"""Recording API — start/stop browser recording sessions, receive events."""

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["recording"])


class RecordingSession(BaseModel):
    id: UUID
    process_id: UUID
    status: str
    target_url: str


class StartRecordingRequest(BaseModel):
    process_id: UUID
    target_url: str


class RecordedEvent(BaseModel):
    timestamp: float
    event_type: str
    target: dict | None = None
    value: str | None = None
    url: str | None = None
    metadata: dict | None = None


# In-memory session store (replaced by DB/Redis in production)
_sessions: dict[UUID, dict] = {}
_events: dict[UUID, list[dict]] = {}


@router.post("/recording/start", response_model=RecordingSession)
async def start_recording(body: StartRecordingRequest) -> dict:
    session_id = uuid4()
    session = {
        "id": session_id,
        "process_id": body.process_id,
        "status": "recording",
        "target_url": body.target_url,
    }
    _sessions[session_id] = session
    _events[session_id] = []
    return session


@router.post("/recording/{session_id}/events")
async def push_events(session_id: UUID, events: list[RecordedEvent]) -> dict:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    if _sessions[session_id]["status"] != "recording":
        raise HTTPException(status_code=400, detail="Session is not recording")
    _events[session_id].extend([e.model_dump() for e in events])
    return {"received": len(events), "total": len(_events[session_id])}


@router.post("/recording/{session_id}/stop")
async def stop_recording(session_id: UUID) -> dict:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    _sessions[session_id]["status"] = "stopped"
    return {
        "session_id": session_id,
        "status": "stopped",
        "event_count": len(_events[session_id]),
    }


@router.get("/recording/{session_id}/events")
async def get_events(session_id: UUID) -> list[dict]:
    if session_id not in _events:
        raise HTTPException(status_code=404, detail="Session not found")
    return _events[session_id]
