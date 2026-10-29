from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.pipeline import Pipeline, PipelineRunItem
from ..models.process import Execution, ExecutionStep, Process, ProcessVersion
from ..schemas.process import (
    ExecutionCreate,
    ExecutionRead,
    ExecutionStepRead,
    ProcessCreate,
    ProcessRead,
    ProcessUpdate,
    VersionCreate,
    VersionRead,
    VersionUpdate,
)

router = APIRouter(tags=["processes"])


# --- Processes ---

@router.post("/processes", response_model=ProcessRead, status_code=status.HTTP_201_CREATED)
async def create_process(body: ProcessCreate, db: AsyncSession = Depends(get_db)) -> Process:
    process = Process(name=body.name, description=body.description, robot_code=body.robot_code)
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


@router.put("/processes/{process_id}", response_model=ProcessRead)
async def update_process(
    process_id: UUID, body: ProcessUpdate, db: AsyncSession = Depends(get_db)
) -> Process:
    process = await db.get(Process, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    if body.name is not None:
        process.name = body.name
    if body.description is not None:
        process.description = body.description
    if body.robot_code is not None:
        process.robot_code = body.robot_code
    db.add(process)
    await db.commit()
    await db.refresh(process)
    return process


async def _workflows_using(db: AsyncSession, process_id: UUID | None = None,
                           version_id: UUID | None = None) -> list[str]:
    """Workflows whose process nodes run this process (or are pinned to this version)."""
    names = []
    for p in (await db.execute(select(Pipeline))).scalars().all():
        for n in (p.graph or {}).get("nodes", []):
            cfg = n.get("config") or {}
            if n.get("type") != "robot.run":
                continue
            if (process_id and cfg.get("process_id") == str(process_id)) or \
                    (version_id and cfg.get("version_id") == str(version_id)):
                names.append(p.name)
                break
    return names


async def _delete_executions(db: AsyncSession, condition) -> None:
    """Executions go with their process/version; workflow run history keeps its rows
    (status, error, data) but loses the link to the deleted execution."""
    ids = select(Execution.id).where(condition)
    await db.execute(update(PipelineRunItem).where(PipelineRunItem.execution_id.in_(ids)).values(execution_id=None))
    await db.execute(delete(ExecutionStep).where(ExecutionStep.execution_id.in_(ids)))
    await db.execute(delete(Execution).where(condition))


@router.delete("/processes/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process(process_id: UUID, db: AsyncSession = Depends(get_db)):
    process = await db.get(Process, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    used_by = await _workflows_using(db, process_id=process_id)
    if used_by:
        raise HTTPException(
            status_code=409,
            detail=f"Processus utilisé par le(s) workflow(s) : {', '.join(used_by)}. "
                   f"Retirez-le de ces workflows avant de le supprimer.",
        )
    await db.execute(update(Pipeline).where(Pipeline.process_id == process_id).values(process_id=None, version_id=None))
    await _delete_executions(db, Execution.process_id == process_id)
    await db.execute(delete(ProcessVersion).where(ProcessVersion.process_id == process_id))
    await db.delete(process)
    await db.commit()


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


@router.put("/processes/{process_id}/versions/{version_id}", response_model=VersionRead)
async def update_version(
    process_id: UUID,
    version_id: UUID,
    body: VersionUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProcessVersion:
    version = await db.get(ProcessVersion, version_id)
    if not version or version.process_id != process_id:
        raise HTTPException(status_code=404, detail="Version not found")
    if body.definition is not None:
        version.definition = body.definition
    if body.status is not None:
        version.status = body.status
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


@router.delete(
    "/processes/{process_id}/versions/{version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_version(
    process_id: UUID, version_id: UUID, db: AsyncSession = Depends(get_db)
):
    version = await db.get(ProcessVersion, version_id)
    if not version or version.process_id != process_id:
        raise HTTPException(status_code=404, detail="Version not found")
    pinned_by = await _workflows_using(db, version_id=version_id)
    if pinned_by:
        raise HTTPException(
            status_code=409,
            detail=f"Version fixée dans le(s) workflow(s) : {', '.join(pinned_by)}",
        )
    await db.execute(update(Pipeline).where(Pipeline.version_id == version_id).values(version_id=None))
    await _delete_executions(db, Execution.version_id == version_id)
    await db.delete(version)
    await db.commit()


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
