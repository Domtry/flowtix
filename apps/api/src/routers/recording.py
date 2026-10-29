"""Recording API — proxies to the browser agent running on the host."""

import os
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.process import ProcessVersion

router = APIRouter(tags=["recording"])

AGENT_URL = os.environ.get("FLOWTIX_BROWSER_AGENT_URL", "http://localhost:9090")

_sessions: dict[str, dict] = {}


class StartRecordingRequest(BaseModel):
    process_id: str
    target_url: str
    browser_path: str | None = None
    action_type: str = "web"
    engine: str = "auto"
    window_title_pattern: str = ""
    keep_session: bool = False


@router.post("/recording/start")
async def start_recording(body: StartRecordingRequest):
    async with httpx.AsyncClient(timeout=30) as client:
        payload: dict = {
                "target_url": body.target_url,
                "process_id": body.process_id,
                "action_type": body.action_type,
                "engine": body.engine,
            }
        if body.browser_path:
            payload["browser_path"] = body.browser_path
        if body.window_title_pattern:
            payload["window_title_pattern"] = body.window_title_pattern
        if body.keep_session:
            payload["keep_session"] = True
        try:
            resp = await client.post(f"{AGENT_URL}/record/start", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(503, "Browser agent not reachable. Start it on the host: cd agents/browser && python run.py")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(exc.response.status_code, exc.response.text)

    data = resp.json()
    session_id = data["session_id"]
    _sessions[session_id] = {
        "id": session_id,
        "process_id": body.process_id,
        "target_url": body.target_url,
        "status": "recording",
    }
    return {"id": session_id, "status": "recording", "process_id": body.process_id, "target_url": body.target_url}


@router.get("/recording/{session_id}/events")
async def get_events(session_id: str):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{AGENT_URL}/record/{session_id}/events")
            resp.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(503, "Browser agent not reachable")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(exc.response.status_code, exc.response.text)
    return resp.json()


@router.post("/recording/{session_id}/stop")
async def stop_recording(session_id: str, db: AsyncSession = Depends(get_db)):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(f"{AGENT_URL}/record/{session_id}/stop")
            resp.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(503, "Browser agent not reachable")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(exc.response.status_code, exc.response.text)

    data = resp.json()
    definition = data.get("definition", {})
    process_id = session["process_id"]

    from sqlalchemy import func, select
    result = await db.execute(
        select(func.coalesce(func.max(ProcessVersion.version), 0))
        .where(ProcessVersion.process_id == process_id)
    )
    max_version = result.scalar() or 0

    version = ProcessVersion(
        process_id=process_id,
        version=max_version + 1,
        schema_version=definition.get("schema_version", "1.0"),
        definition=definition,
        status="draft",
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)

    _sessions[session_id]["status"] = "stopped"

    return {
        "session_id": session_id,
        "status": "stopped",
        "event_count": data.get("event_count", 0),
        "version_id": str(version.id),
        "version": version.version,
    }
