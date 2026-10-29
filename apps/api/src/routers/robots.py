"""Robot management — each robot targets a specific platform (ORASS, Sanlam, etc.)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.process import AppModule

router = APIRouter(prefix="/robots", tags=["robots"])


def _is_uuid(val: str) -> bool:
    try:
        UUID(val)
        return True
    except ValueError:
        return False


async def _find_robot(robot_id: str, db: AsyncSession) -> AppModule | None:
    if _is_uuid(robot_id):
        stmt = select(AppModule).where((AppModule.code == robot_id) | (AppModule.id == robot_id))
    else:
        stmt = select(AppModule).where(AppModule.code == robot_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


class RobotCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    action_type: str = "web"
    engine: str = "subprocess"
    executable_path: str = ""
    default_url: str | None = None
    window_title_pattern: str | None = None
    config: dict = {}


class RobotUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    action_type: str | None = None
    engine: str | None = None
    executable_path: str | None = None
    default_url: str | None = None
    window_title_pattern: str | None = None
    config: dict | None = None


@router.get("/")
async def list_robots(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppModule).order_by(AppModule.name))
    return list(result.scalars().all())


@router.get("/{robot_id}")
async def get_robot(robot_id: str, db: AsyncSession = Depends(get_db)):
    robot = await _find_robot(robot_id, db)
    if not robot:
        raise HTTPException(404, f"Robot '{robot_id}' not found")
    return robot


@router.post("/", status_code=201)
async def create_robot(body: RobotCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(AppModule).where(AppModule.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Robot '{body.code}' already exists")
    robot = AppModule(**body.model_dump())
    db.add(robot)
    await db.commit()
    await db.refresh(robot)
    return robot


@router.put("/{robot_id}")
async def update_robot(robot_id: str, body: RobotUpdate, db: AsyncSession = Depends(get_db)):
    robot = await _find_robot(robot_id, db)
    if not robot:
        raise HTTPException(404, f"Robot '{robot_id}' not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(robot, field, value)
    db.add(robot)
    await db.commit()
    await db.refresh(robot)
    return robot


@router.delete("/{robot_id}", status_code=204)
async def delete_robot(robot_id: str, db: AsyncSession = Depends(get_db)):
    robot = await _find_robot(robot_id, db)
    if not robot:
        raise HTTPException(404, f"Robot '{robot_id}' not found")
    await db.delete(robot)
    await db.commit()
