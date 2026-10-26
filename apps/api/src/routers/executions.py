"""Execution management routes — start, pause, resume, cancel, live state."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.process import Execution, ProcessVersion
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
        raise HTTPException(status_code=400, detail=f"Execution is {execution.status}, expected created")

    version = await db.get(ProcessVersion, execution.version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    workflow_id = await _execution_service.start_execution(
        execution_id=str(execution.id),
        process_id=str(execution.process_id),
        version_id=str(execution.version_id),
        definition=version.definition,
        inputs=execution.inputs or {},
    )

    execution.status = "queued"
    await db.commit()

    return {"workflow_id": workflow_id, "status": "queued"}


@router.post("/executions/{execution_id}/pause")
async def pause_execution(execution_id: UUID) -> dict:
    await _execution_service.pause_execution(str(execution_id))
    return {"status": "pause_signal_sent"}


@router.post("/executions/{execution_id}/resume")
async def resume_execution(execution_id: UUID) -> dict:
    await _execution_service.resume_execution(str(execution_id))
    return {"status": "resume_signal_sent"}


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: UUID) -> dict:
    await _execution_service.cancel_execution(str(execution_id))
    return {"status": "cancel_signal_sent"}


@router.get("/executions/{execution_id}/state")
async def get_execution_state(execution_id: UUID) -> dict:
    try:
        state = await _execution_service.get_execution_state(str(execution_id))
        return state
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not query workflow: {exc}")
