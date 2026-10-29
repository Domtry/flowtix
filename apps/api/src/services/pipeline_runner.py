"""Workflow runner: one background worker executing queued runs, plus a scheduler
that queues runs for enabled schedule triggers.

Runs are strictly sequential: there is one desktop (mouse, keyboard). The desktop
lock in ExecutionService also serialises robot steps with manual Run clicks.
"""

import asyncio
import copy
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session
from ..models.pipeline import Pipeline, PipelineFile, PipelineRun, PipelineRunItem
from ..models.process import Execution, Process, ProcessVersion
from . import cron
from .execution_service import ExecutionService
from .pipeline_source import SourceError, parse_source
from .workflow.engine import WorkflowCancelled, WorkflowEngine, WorkflowFailed, sample
from .workflow.nodes import EXECUTORS, apply_values, keep_session

logger = logging.getLogger(__name__)

ACTIVE_RUN_STATUSES = ("queued", "running", "cancelling")
WORKER_IDLE_POLL = 2.0
SCHEDULER_TICK = 20.0  # < 60 s so every minute is evaluated


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def resolve_version(db: AsyncSession, process_id, version_id=None) -> ProcessVersion | None:
    if version_id:
        return await db.get(ProcessVersion, version_id)
    result = await db.execute(
        select(ProcessVersion)
        .where(ProcessVersion.process_id == process_id)
        .order_by(ProcessVersion.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def has_active_run(db: AsyncSession, pipeline_id) -> bool:
    result = await db.execute(
        select(func.count()).select_from(PipelineRun).where(
            PipelineRun.pipeline_id == pipeline_id,
            PipelineRun.status.in_(ACTIVE_RUN_STATUSES),
        )
    )
    return (result.scalar() or 0) > 0


def final_status(ends: list[dict], robot_failures: int) -> tuple[str, str | None]:
    """The closing points reached decide the outcome: any item ending on a failure end
    fails the run (partial if others ended well); otherwise robot failures make it partial."""
    failed = [e for e in ends if e["result"] == "failure"]
    succeeded = [e for e in ends if e["result"] == "success"]
    if failed:
        message = "; ".join(f"{e['name']} ({e['count']}) : {e['message']}" if e["message"]
                            else f"{e['name']} ({e['count']})" for e in failed)
        return ("partial" if succeeded else "failed"), message
    if robot_failures:
        return "partial", None
    return "succeeded", None


class RunContext:
    """What workflow nodes need from the outside world, for one run."""

    def __init__(self, db: AsyncSession, run: PipelineRun, pipeline: Pipeline,
                 executions: ExecutionService) -> None:
        self.db = db
        self.run = run
        self.pipeline = pipeline
        self.executions = executions
        self.results: dict[str, dict] = {}
        self.ends: list[dict] = []  # closing points reached, filled by the Fin node
        self.robot_rows = 0
        self._versions: dict[tuple, tuple] = {}

    async def check_cancel(self) -> None:
        await self.db.refresh(self.run, ["status"])
        if self.run.status == "cancelling":
            raise WorkflowCancelled()

    async def record(self, node_id: str, items_in: list, outputs: dict, error: str | None,
                     duration_ms: int) -> None:
        r = self.results.setdefault(node_id, {"status": "success", "runs": 0, "items_in": 0,
                                              "items_out": {}, "duration_ms": 0})
        r["runs"] += 1
        r["items_in"] += len(items_in)
        r["duration_ms"] += duration_ms
        r["sample_in"] = sample(items_in)
        for port, items in outputs.items():
            r["items_out"][port] = r["items_out"].get(port, 0) + len(items)
            if items:
                r.setdefault("sample_out", {})[port] = sample(items)
        if error:
            r["status"], r["error"] = "error", error
        elif outputs.get("error") and r["status"] != "error":
            r["status"] = "warning"  # some items went to the error output
        self.run.node_results = copy.deepcopy(self.results)  # new object so the JSON column is saved
        await self.db.commit()

    async def _process(self, process_id, version_id) -> tuple[Process, ProcessVersion]:
        key = (process_id, version_id)
        if key not in self._versions:
            process = await self.db.get(Process, process_id) if process_id else None
            if not process:
                raise ValueError("Le robot (processus) de ce bloc n'existe plus")
            version = await resolve_version(self.db, process.id, version_id)
            if not version:
                raise ValueError(f"Le processus « {process.name} » n'a aucune version enregistrée")
            self._versions[key] = (process, version)
        return self._versions[key]

    async def run_robot(self, node: dict, process_id, version_id, values: dict,
                        item: dict, session: dict | None = None) -> tuple[bool, str | None, str]:
        process, version = await self._process(process_id, version_id)
        definition = apply_values(version.definition, values)
        if session and session.get("keep"):
            definition = keep_session(definition, session.get("start_step_id"))
        execution = Execution(process_id=process.id, version_id=version.id, status="created", inputs=item)
        self.db.add(execution)
        await self.db.flush()
        row = PipelineRunItem(run_id=self.run.id, node_id=node["id"], row_index=self.robot_rows,
                              row_data=item, execution_id=execution.id, status="running", started_at=_now())
        self.robot_rows += 1
        self.db.add(row)
        await self.db.commit()

        # every process of the workflow runs on the workflow's robot
        robot_code = self.pipeline.robot_code or process.robot_code
        await self.executions.run_and_wait(str(execution.id), definition, robot_code, item)

        await self.db.refresh(execution)
        row.completed_at = _now()
        if execution.status == "succeeded":
            row.status = "succeeded"
            self.run.succeeded += 1
        elif execution.status == "cancelled":
            row.status, row.error = "skipped", "Annulé"
            await self.db.commit()
            raise WorkflowCancelled()
        else:
            row.status = "failed"
            row.error = (execution.error or {}).get("message") or f"Statut {execution.status}"
            self.run.failed += 1
        await self.db.commit()
        return row.status == "succeeded", row.error, str(execution.id)

    async def read_file(self, file_id, sheet) -> list[dict]:
        f = await self.db.get(PipelineFile, file_id) if file_id else None
        if not f or f.pipeline_id != self.pipeline.id:
            raise ValueError("Le fichier de ce bloc n'existe plus : rechargez-le")
        try:
            _, rows = parse_source(f.filename, f.content, sheet)
        except SourceError as exc:
            raise ValueError(str(exc)) from exc
        return rows

    async def save_output_file(self, filename: str, content: bytes) -> None:
        self.db.add(PipelineFile(pipeline_id=self.pipeline.id, run_id=self.run.id, kind="output",
                                 filename=filename, content=content))
        await self.db.commit()

    async def smtp_settings(self) -> dict | None:
        from ..routers.integrations import load_smtp
        return await load_smtp(self.db, with_password=True)


class PipelineRunner:
    def __init__(self) -> None:
        self._executions = ExecutionService()
        self._wake = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._worker(), name="workflow-worker"),
            asyncio.create_task(self._scheduler(), name="workflow-scheduler"),
        ]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def wake(self) -> None:
        self._wake.set()

    async def create_run(self, db: AsyncSession, pipeline: Pipeline, trigger: str,
                         start_node_id: str, items: list[dict]) -> PipelineRun:
        run = PipelineRun(pipeline_id=pipeline.id, trigger=trigger, total_rows=len(items),
                          start_node_id=start_node_id, start_items=items, node_results={})
        db.add(run)
        await db.commit()
        await db.refresh(run)
        self._wake.set()
        logger.info("Workflow %s: run %s queued (%s, %d items)", pipeline.id, run.id, trigger, len(items))
        return run

    # ------------------------------------------------------------------ worker

    async def _worker(self) -> None:
        await self._recover()
        while True:
            run_id = await self._next_queued()
            if run_id is None:
                try:
                    await asyncio.wait_for(self._wake.wait(), WORKER_IDLE_POLL)
                except TimeoutError:
                    pass
                self._wake.clear()
                continue
            try:
                await self._execute_run(run_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Workflow run %s crashed", run_id)
                async with async_session() as db:
                    run = await db.get(PipelineRun, run_id)
                    if run:
                        run.status, run.error, run.completed_at = "failed", str(exc), _now()
                        await db.commit()

    async def _recover(self) -> None:
        """A run interrupted by a server restart can't resume mid-graph: close it."""
        async with async_session() as db:
            result = await db.execute(
                select(PipelineRun).where(PipelineRun.status.in_(("running", "cancelling"))))
            for run in result.scalars():
                run.status = "failed" if run.status == "running" else "cancelled"
                run.error = "Interrompu par un redémarrage du serveur"
                run.completed_at = _now()
            items = await db.execute(select(PipelineRunItem).where(PipelineRunItem.status == "running"))
            for item in items.scalars():
                item.status, item.error = "failed", "Interrompu par un redémarrage du serveur"
            await db.commit()

    async def _next_queued(self):
        async with async_session() as db:
            result = await db.execute(
                select(PipelineRun.id).where(PipelineRun.status == "queued")
                .order_by(PipelineRun.created_at).limit(1))
            return result.scalar_one_or_none()

    async def _execute_run(self, run_id) -> None:
        async with async_session() as db:
            run = await db.get(PipelineRun, run_id)
            pipeline = await db.get(Pipeline, run.pipeline_id) if run else None
            if not run or not pipeline:
                return
            run.status, run.started_at = "running", _now()
            await db.commit()

            ctx = RunContext(db, run, pipeline, self._executions)
            engine = WorkflowEngine(pipeline.graph or {}, EXECUTORS, ctx)
            try:
                await engine.run(run.start_node_id, list(run.start_items or [{}]))
                run.status, run.error = final_status(ctx.ends, run.failed)
            except WorkflowCancelled:
                run.status = "cancelled"
            except WorkflowFailed as exc:
                run.status, run.error = "failed", exc.message
                if exc.node_id:
                    node = next((n for n in pipeline.graph.get("nodes", []) if n["id"] == exc.node_id), None)
                    run.error = f"{(node or {}).get('name') or exc.node_id} : {exc.message}"
            run.completed_at = _now()
            await db.commit()
            logger.info("Workflow run %s finished: %s", run.id, run.status)

    # --------------------------------------------------------------- scheduler

    async def _scheduler(self) -> None:
        while True:
            await asyncio.sleep(SCHEDULER_TICK)
            try:
                await self._tick(_now().replace(second=0, microsecond=0))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Workflow scheduler tick failed")

    async def _tick(self, minute: datetime) -> None:
        async with async_session() as db:
            for pipeline in (await db.execute(select(Pipeline))).scalars().all():
                for node in (pipeline.graph or {}).get("nodes", []):
                    cfg = node.get("config") or {}
                    if node.get("type") != "trigger.schedule" or not cfg.get("enabled") or not cfg.get("cron"):
                        continue
                    state = dict(pipeline.schedule_state or {})
                    if state.get(node["id"]) == minute.isoformat():
                        continue
                    try:
                        if not cron.matches(cfg["cron"], minute):
                            continue
                    except ValueError:
                        continue
                    state[node["id"]] = minute.isoformat()
                    pipeline.schedule_state = state
                    await db.commit()
                    if await has_active_run(db, pipeline.id):
                        logger.info("Workflow %s: schedule skipped, a run is still active", pipeline.id)
                        continue
                    await self.create_run(db, pipeline, "schedule", node["id"],
                                          [{"declenche_le": minute.isoformat()}])


runner = PipelineRunner()
