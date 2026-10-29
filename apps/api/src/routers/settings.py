"""Settings API — key/value store for user preferences."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.process import Setting
from ..schemas.process import SettingsRead, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=list[SettingsRead])
async def list_settings(db: AsyncSession = Depends(get_db)):
    # integration settings (SMTP, …) hold secrets: served by /integrations only
    result = await db.execute(select(Setting).where(Setting.key.not_like("integration.%")))
    return list(result.scalars().all())


@router.get("/{key}")
async def get_setting(key: str, db: AsyncSession = Depends(get_db)):
    if key.startswith("integration."):
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return {"key": setting.key, "value": setting.value}


@router.put("/{key}")
async def upsert_setting(
    key: str, body: SettingsUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = body.value
    else:
        setting = Setting(key=key, value=body.value)
    db.add(setting)
    await db.commit()
    await db.refresh(setting)
    return {"key": setting.key, "value": setting.value}


@router.delete("/{key}", status_code=204)
async def delete_setting(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    await db.delete(setting)
    await db.commit()
