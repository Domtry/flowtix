"""Temporal activity definitions — the units of work executed by workers.

Activities run outside the deterministic workflow sandbox and can perform I/O:
database writes, robot communication, file storage, etc.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from temporalio import activity


# --- Activity input/output contracts ---

@dataclass
class ExecuteStepInput:
    execution_id: str
    step: dict
    inputs: dict
    step_index: int


@dataclass
class ExecuteStepResult:
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: int = 0
    screenshot_key: str | None = None


@dataclass
class UpdateExecutionStatusInput:
    execution_id: str
    status: str
    outputs: dict | None = None
    error: str | None = None


@dataclass
class SaveStepResultInput:
    execution_id: str
    step_id: str
    step_index: int
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: int = 0
    screenshot_key: str | None = None


@dataclass
class GenerateReportInput:
    execution_id: str
    status: str
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0


# --- Activities ---

@activity.defn
async def execute_step(input: ExecuteStepInput) -> ExecuteStepResult:
    """Execute a single process step via the appropriate robot.

    In the MVP, this dispatches to the browser replay engine directly.
    In production, this would send the step to an available robot via
    the orchestrator-robot protocol.
    """
    step = input.step
    step_type = step.get("type", "")
    start = time.monotonic()

    try:
        # Import here to avoid loading Playwright in the workflow sandbox
        from agents.browser.src.replay import ReplayEngine

        engine = ReplayEngine(headless=True)
        # Wrap single step as a mini-scenario
        mini_scenario = {
            "process": {
                "id": "single-step",
                "name": "single-step",
                "steps": [step],
            }
        }
        replay_result = await engine.replay(mini_scenario, inputs=input.inputs)
        duration = int((time.monotonic() - start) * 1000)

        if replay_result.success:
            return ExecuteStepResult(
                success=True,
                duration_ms=duration,
                result={"step_type": step_type},
            )
        else:
            error_msg = replay_result.steps[0].error if replay_result.steps else "Unknown error"
            screenshot = replay_result.steps[0].screenshot if replay_result.steps else None
            screenshot_key = None
            if screenshot:
                screenshot_key = f"{input.execution_id}/{input.step_index}/{int(time.time())}.png"
            return ExecuteStepResult(
                success=False,
                error=error_msg,
                duration_ms=duration,
                screenshot_key=screenshot_key,
            )
    except Exception as exc:
        duration = int((time.monotonic() - start) * 1000)
        return ExecuteStepResult(
            success=False,
            error=str(exc),
            duration_ms=duration,
        )


@activity.defn
async def update_execution_status(input: UpdateExecutionStatusInput) -> None:
    """Update execution status in the database.

    In the MVP, this uses direct DB access. In production, this would
    go through the API or a shared database service.
    """
    activity.logger.info(
        "Updating execution %s to status %s", input.execution_id, input.status
    )
    # TODO: Direct DB update when database layer is integrated into worker
    # For now, log the state change (the API will be extended with an internal endpoint)


@activity.defn
async def save_step_result(input: SaveStepResultInput) -> None:
    """Persist step execution result to the database."""
    activity.logger.info(
        "Step %s (index %d) for execution %s: success=%s, duration=%dms",
        input.step_id,
        input.step_index,
        input.execution_id,
        input.success,
        input.duration_ms,
    )
    # TODO: Direct DB insert into execution_steps table


@activity.defn
async def generate_report(input: GenerateReportInput) -> dict:
    """Generate an execution report."""
    report = {
        "execution_id": input.execution_id,
        "status": input.status,
        "total_steps": input.total_steps,
        "completed_steps": input.completed_steps,
        "failed_steps": input.failed_steps,
        "success_rate": (
            round(input.completed_steps / input.total_steps * 100, 1)
            if input.total_steps > 0
            else 0
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    activity.logger.info("Report for execution %s: %s", input.execution_id, report)
    return report
