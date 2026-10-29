"""Execution management routes — start, pause, resume, cancel, live state."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.process import Execution, ExecutionStep, Process, ProcessVersion
from ..schemas.process import ExecutionRead
from ..services.execution_service import ExecutionService

router = APIRouter(tags=["executions"])

_execution_service = ExecutionService()


@router.post("/executions/{execution_id}/start")
async def start_execution(
    execution_id: UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    execution = await db.get(Execution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if execution.status != "created":
        raise HTTPException(
            status_code=400, detail=f"Execution is {execution.status}, expected created"
        )

    version = await db.get(ProcessVersion, execution.version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    process = await db.get(Process, execution.process_id)
    robot_code = process.robot_code if process else None

    await _execution_service.start_execution(
        execution_id=str(execution.id),
        definition=version.definition,
        robot_code=robot_code,
        inputs=execution.inputs,
    )

    return {"status": "running"}


@router.post("/executions/{execution_id}/pause")
async def pause_execution(execution_id: UUID) -> dict:
    await _execution_service.pause_execution(str(execution_id))
    return {"status": "paused"}


@router.post("/executions/{execution_id}/resume")
async def resume_execution(execution_id: UUID) -> dict:
    await _execution_service.resume_execution(str(execution_id))
    return {"status": "running"}


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: UUID) -> dict:
    await _execution_service.cancel_execution(str(execution_id))
    return {"status": "cancelled"}


@router.get("/executions/{execution_id}/state")
async def get_execution_state(
    execution_id: UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    execution = await db.get(Execution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    result = await db.execute(
        select(ExecutionStep)
        .where(ExecutionStep.execution_id == execution_id)
        .order_by(ExecutionStep.step_index)
    )
    steps = list(result.scalars().all())

    running_step = next((s for s in steps if s.status == "running"), None)

    return {
        "execution_id": str(execution.id),
        "status": execution.status,
        "paused": execution.status == "paused",
        "current_step_id": execution.current_step_id,
        "current_step_index": running_step.step_index if running_step else None,
        "completed_steps": [s.step_id for s in steps if s.status == "succeeded"],
        "failed_steps": [s.step_id for s in steps if s.status == "failed"],
        "total_steps": len(steps),
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "error": execution.error,
    }
