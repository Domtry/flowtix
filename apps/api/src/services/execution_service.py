"""Execution service — delegates step execution to the browser agent on the host."""

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from ..core.database import async_session
from ..models.process import AppModule, Execution, ExecutionStep

logger = logging.getLogger(__name__)

AGENT_URL = os.environ.get("FLOWTIX_BROWSER_AGENT_URL", "http://localhost:9090")

# One desktop = one mouse and one keyboard: replays must never overlap, whether
# started from the Run button or by a pipeline.
DESKTOP_LOCK = asyncio.Lock()


def _normalize_step(step_def: dict) -> dict:
    """Adapt Step Builder format to ReplayEngine format."""
    step_type = step_def.get("type", "")
    target = step_def.get("target") or {}
    value = step_def.get("value")
    params = step_def.get("params") or {}

    if step_type == "browser.navigate" and value and "url" not in params:
        params["url"] = value

    if step_type == "keyboard.press" and value and "key" not in params:
        params["key"] = value

    if step_type == "browser.wait" and value and "event" not in params:
        params["event"] = "load"
        try:
            step_def["timeout_ms"] = int(value)
        except (ValueError, TypeError):
            pass

    if step_type == "ui.scroll" and not params:
        params = {"x": 0, "y": 0}

    result = dict(step_def)
    result["params"] = params
    result["target"] = target
    return result


class ExecutionService:
    def __init__(self) -> None:
        self._running: dict[str, asyncio.Task] = {}

    async def start_execution(
        self, execution_id: str, definition: dict, robot_code: str | None = None,
        inputs: dict | None = None,
    ) -> None:
        task = asyncio.create_task(self.run_and_wait(execution_id, definition, robot_code, inputs))
        self._running[execution_id] = task

    async def run_and_wait(
        self, execution_id: str, definition: dict, robot_code: str | None = None,
        inputs: dict | None = None,
    ) -> None:
        """Run on the desktop once it is free, and return when the replay has ended."""
        async with async_session() as db:
            execution = await db.get(Execution, execution_id)
            if execution and DESKTOP_LOCK.locked():
                execution.status = "queued"
                await db.commit()
        async with DESKTOP_LOCK:
            await self._run_via_agent(execution_id, definition, robot_code, inputs)

    async def _run_via_agent(
        self, execution_id: str, definition: dict, robot_code: str | None = None,
        inputs: dict | None = None,
    ) -> None:
        """Send the definition to the browser agent for replay and track progress."""
        proc = definition.get("process", definition)
        steps = proc.get("steps", [])

        async with async_session() as db:
            execution = await db.get(Execution, execution_id)
            if not execution:
                return
            if execution.status == "cancelled":
                return
            execution.status = "running"
            execution.started_at = datetime.now(timezone.utc)
            await db.commit()

            robot_engine = "auto"
            robot_browser_path = ""
            if robot_code:
                stmt = select(AppModule).where(AppModule.code == robot_code)
                row = await db.execute(stmt)
                robot = row.scalar_one_or_none()
                if robot:
                    robot_engine = robot.engine or "auto"
                    robot_browser_path = robot.executable_path or ""

            normalized_steps = [_normalize_step(s) for s in steps]
            normalized_def = dict(definition)
            if "process" in normalized_def:
                normalized_def["process"] = dict(normalized_def["process"])
                normalized_def["process"]["steps"] = normalized_steps
            else:
                normalized_def["steps"] = normalized_steps

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(f"{AGENT_URL}/replay/start", json={
                        "execution_id": execution_id,
                        "definition": normalized_def,
                        "headless": False,
                        "engine": robot_engine,
                        "browser_path": robot_browser_path,
                        "inputs": inputs or {},
                    })
                    resp.raise_for_status()
                    replay_data = resp.json()
                    replay_id = replay_data.get("replay_id", execution_id)
            except Exception as exc:
                logger.error("Cannot reach browser agent: %s", exc)
                execution.status = "failed"
                execution.error = {"message": f"Browser agent unreachable: {exc}", "type": "AgentUnreachable"}
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()
                self._running.pop(execution_id, None)
                return

            for i, step_def in enumerate(steps):
                step = ExecutionStep(
                    execution_id=execution_id,
                    step_id=step_def.get("id", f"step-{i+1}"),
                    step_index=i,
                    status="pending",
                    attempt=1,
                    started_at=datetime.now(timezone.utc),
                )
                db.add(step)
            await db.commit()

            while True:
                await asyncio.sleep(1)
                await db.refresh(execution)
                if execution.status == "cancelled":
                    await _cancel_on_agent(replay_id)
                    break

                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.get(f"{AGENT_URL}/replay/{replay_id}/status")
                        resp.raise_for_status()
                        status_data = resp.json()
                except Exception:
                    continue

                agent_status = status_data.get("status", "running")
                result = status_data.get("result")

                if result and "steps" in result:
                    for sr in result["steps"]:
                        stmt = select(ExecutionStep).where(
                            ExecutionStep.execution_id == execution_id,
                            ExecutionStep.step_id == sr["step_id"],
                        )
                        row = await db.execute(stmt)
                        db_step = row.scalar_one_or_none()
                        if db_step:
                            db_step.status = "succeeded" if sr["success"] else "failed"
                            db_step.completed_at = datetime.now(timezone.utc)
                            db_step.result = {"duration_ms": sr.get("duration_ms", 0)}
                            if sr.get("error"):
                                db_step.error = {"message": sr["error"], "type": "ReplayError"}
                            execution.current_step_id = sr["step_id"]
                    await db.commit()

                if agent_status in ("succeeded", "failed"):
                    execution.status = agent_status
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.current_step_id = None
                    if result and not result.get("success", True):
                        first_error = next(
                            (s.get("error") for s in result.get("steps", []) if s.get("error")),
                            None,
                        ) or result.get("error") or "One or more steps failed"
                        execution.error = {"message": first_error, "type": "ReplayError"}
                    await db.commit()
                    break

        self._running.pop(execution_id, None)

    async def pause_execution(self, execution_id: str) -> None:
        async with async_session() as db:
            execution = await db.get(Execution, execution_id)
            if execution and execution.status == "running":
                execution.status = "paused"
                await db.commit()

    async def resume_execution(self, execution_id: str) -> None:
        async with async_session() as db:
            execution = await db.get(Execution, execution_id)
            if execution and execution.status == "paused":
                execution.status = "running"
                await db.commit()

    async def cancel_execution(self, execution_id: str) -> None:
        async with async_session() as db:
            execution = await db.get(Execution, execution_id)
            if execution and execution.status in ("running", "paused", "queued"):
                execution.status = "cancelled"
                await db.commit()
        task = self._running.pop(execution_id, None)
        if task:
            task.cancel()
        await _cancel_on_agent(execution_id)


async def _cancel_on_agent(replay_id: str) -> None:
    """Stop the replay on the desktop, so the next one can't overlap with it."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{AGENT_URL}/replay/{replay_id}/cancel")
    except Exception as exc:
        logger.warning("Could not cancel replay %s on agent: %s", replay_id, exc)
