from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.process import Process
from ..schemas.process import ProcessCreate, ProcessRead

router = APIRouter(tags=["processes"])


@router.post("/processes", response_model=ProcessRead, status_code=status.HTTP_201_CREATED)
async def create_process(
    body: ProcessCreate, db: AsyncSession = Depends(get_db)
) -> Process:
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
