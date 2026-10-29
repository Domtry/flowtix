"""Integration settings used by workflow nodes (SMTP for e-mail notifications)."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import secrets
from ..core.database import get_db
from ..models.process import Setting
from ..services.workflow.nodes import _send_mail

router = APIRouter(prefix="/integrations", tags=["integrations"])

SMTP_KEY = "integration.smtp"


class SmtpUpdate(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    security: str = Field(default="starttls", pattern="^(starttls|ssl|none)$")
    username: str = ""
    # None keeps the stored password, "" removes it
    password: str | None = None
    sender: str = Field(min_length=3, max_length=255)


class SmtpTest(BaseModel):
    to: str = Field(min_length=3, max_length=255)


async def load_smtp(db: AsyncSession, with_password: bool = False) -> dict | None:
    row = (await db.execute(select(Setting).where(Setting.key == SMTP_KEY))).scalar_one_or_none()
    if not row or not row.value:
        return None
    data = json.loads(row.value)
    enc = data.pop("password_enc", "")
    data["has_password"] = bool(enc)
    if with_password:
        data["password"] = secrets.decrypt(enc) if enc else ""
    return data


@router.get("/smtp")
async def get_smtp(db: AsyncSession = Depends(get_db)) -> dict:
    return await load_smtp(db) or {"configured": False}


@router.put("/smtp")
async def put_smtp(body: SmtpUpdate, db: AsyncSession = Depends(get_db)) -> dict:
    row = (await db.execute(select(Setting).where(Setting.key == SMTP_KEY))).scalar_one_or_none()
    previous = json.loads(row.value) if row and row.value else {}
    data = body.model_dump(exclude={"password"})
    if body.password is None:
        data["password_enc"] = previous.get("password_enc", "")
    else:
        data["password_enc"] = secrets.encrypt(body.password) if body.password else ""
    if row:
        row.value = json.dumps(data)
    else:
        db.add(Setting(key=SMTP_KEY, value=json.dumps(data)))
    await db.commit()
    return await load_smtp(db) or {}


@router.post("/smtp/test")
async def test_smtp(body: SmtpTest, db: AsyncSession = Depends(get_db)) -> dict:
    smtp = await load_smtp(db, with_password=True)
    if not smtp:
        raise HTTPException(400, "Serveur e-mail non configuré")
    try:
        await asyncio.get_running_loop().run_in_executor(
            None, _send_mail, smtp, [body.to], "FlowtTix — e-mail de test",
            "La configuration du serveur e-mail de FlowtTix fonctionne.",
        )
    except Exception as exc:
        raise HTTPException(400, f"Échec de l'envoi : {exc}") from exc
    return {"sent": True}
