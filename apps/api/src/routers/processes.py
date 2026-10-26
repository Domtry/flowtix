from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.process import Execution, ExecutionStep, Process, ProcessVersion
from ..schemas.process import (
    ExecutionCreate,
    ExecutionRead,
    ExecutionStepRead,
    ProcessCreate,
    ProcessRead,
    VersionCreate,
    VersionRead,
)

router = APIRouter(tags=["processes"])


# --- Processes ---

@router.post("/processes", response_model=ProcessRead, status_code=status.HTTP_201_CREATED)
async def create_process(body: ProcessCreate, db: AsyncSession = Depends(get_db)) -> Process:
    process = Process(name=body.name, description=body.description)
    db.add(process)
    await db.commit()
    await db.refresh(process)
    return process


@router.get("/processes", response_model=list[ProcessRead])
async def list_processes(db: AsyncSession = Depends(get_db)) -> list[Process]:
    result = await db.execute(select(Process).order_by(Process.created_at.desc()))
    return list(result.scalars().all())


@router.get("/processes/{process_id}", response_model=ProcessRead)
async def get_process(process_id: UUID, db: AsyncSession = Depends(get_db)) -> Process:
    process = await db.get(Process, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return process


# --- Versions ---

@router.post(
    "/processes/{process_id}/versions",
    response_model=VersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    process_id: UUID, body: VersionCreate, db: AsyncSession = Depends(get_db)
) -> ProcessVersion:
    process = await db.get(Process, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    max_version = await db.execute(
        select(func.coalesce(func.max(ProcessVersion.version), 0)).where(
            ProcessVersion.process_id == process_id
        )
    )
    next_version = max_version.scalar_one() + 1

    version = ProcessVersion(
        process_id=process_id,
        version=next_version,
        definition=body.definition,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


@router.get("/processes/{process_id}/versions", response_model=list[VersionRead])
async def list_versions(
    process_id: UUID, db: AsyncSession = Depends(get_db)
) -> list[ProcessVersion]:
    result = await db.execute(
        select(ProcessVersion)
        .where(ProcessVersion.process_id == process_id)
        .order_by(ProcessVersion.version.desc())
    )
    return list(result.scalars().all())


@router.get("/processes/{process_id}/versions/{version_id}", response_model=VersionRead)
async def get_version(
    process_id: UUID, version_id: UUID, db: AsyncSession = Depends(get_db)
) -> ProcessVersion:
    version = await db.get(ProcessVersion, version_id)
    if not version or version.process_id != process_id:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


# --- Executions ---

@router.post(
    "/processes/{process_id}/executions",
    response_model=ExecutionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_execution(
    process_id: UUID, body: ExecutionCreate, db: AsyncSession = Depends(get_db)
) -> Execution:
    version = await db.get(ProcessVersion, body.version_id)
    if not version or version.process_id != process_id:
        raise HTTPException(status_code=404, detail="Version not found")

    execution = Execution(
        process_id=process_id,
        version_id=body.version_id,
        inputs=body.inputs,
        status="created",
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    return execution


@router.get("/processes/{process_id}/executions", response_model=list[ExecutionRead])
async def list_executions(
    process_id: UUID, db: AsyncSession = Depends(get_db)
) -> list[Execution]:
    result = await db.execute(
        select(Execution)
        .where(Execution.process_id == process_id)
        .order_by(Execution.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/executions/{execution_id}", response_model=ExecutionRead)
async def get_execution(
    execution_id: UUID, db: AsyncSession = Depends(get_db)
) -> Execution:
    execution = await db.get(Execution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.get("/executions/{execution_id}/steps", response_model=list[ExecutionStepRead])
async def list_execution_steps(
    execution_id: UUID, db: AsyncSession = Depends(get_db)
) -> list[ExecutionStep]:
    result = await db.execute(
        select(ExecutionStep)
        .where(ExecutionStep.execution_id == execution_id)
        .order_by(ExecutionStep.step_index)
    )
    return list(result.scalars().all())
