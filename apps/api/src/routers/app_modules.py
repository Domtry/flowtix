"""App Modules API — reusable application profiles for recording/replay."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.process import AppModule

router = APIRouter(prefix="/app-modules", tags=["app-modules"])


class AppModuleCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    action_type: str = "web"
    engine: str = "auto"
    executable_path: str = ""
    default_url: str | None = None
    window_title_pattern: str | None = None
    config: dict = {}


class AppModuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    action_type: str | None = None
    engine: str | None = None
    executable_path: str | None = None
    default_url: str | None = None
    window_title_pattern: str | None = None
    config: dict | None = None


@router.get("/")
async def list_modules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppModule).order_by(AppModule.name))
    return list(result.scalars().all())


@router.get("/{code}")
async def get_module(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppModule).where(AppModule.code == code))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, f"Module '{code}' not found")
    return module


@router.post("/", status_code=201)
async def create_module(body: AppModuleCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(AppModule).where(AppModule.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Module '{body.code}' already exists")
    module = AppModule(**body.model_dump())
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return module


@router.put("/{code}")
async def update_module(code: str, body: AppModuleUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppModule).where(AppModule.code == code))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, f"Module '{code}' not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(module, field, value)
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return module


@router.delete("/{code}", status_code=204)
async def delete_module(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppModule).where(AppModule.code == code))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, f"Module '{code}' not found")
    await db.delete(module)
    await db.commit()
