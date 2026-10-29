"""Browser Agent — runs on the HOST machine, controls a real browser.

Exposes an HTTP API for:
- Recording sessions (Playwright for Chromium-based, Selenium for Firefox/others)
- Replaying process definitions
"""

import asyncio
import logging
import os
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .recorder import BrowserRecorder, RecordedEvent
from .selenium_recorder import SeleniumRecorder
from .subprocess_recorder import SubprocessRecorder, _beep
from .replay import ReplayEngine, ReplayResult
from .subprocess_replay import SubprocessReplayEngine, request_stop
from .transformer import transform_events

BROWSER_PATH = os.environ.get(
    "FLOWTIX_BROWSER_PATH",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)

logger = logging.getLogger(__name__)

app = FastAPI(title="FlowtTix Browser Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_recorders: dict[str, BrowserRecorder | SeleniumRecorder | SubprocessRecorder] = {}
_session_meta: dict[str, dict] = {}
_replays: dict[str, dict] = {}

CHROMIUM_KEYWORDS = {"edge", "msedge", "chrome", "chromium", "brave", "opera", "vivaldi"}


def _is_chromium_based(path: str) -> bool:
    lower = path.lower()
    return any(kw in lower for kw in CHROMIUM_KEYWORDS)


class StartRequest(BaseModel):
    target_url: str
    process_id: str = ""
    browser_path: str = ""
    action_type: str = "web"
    engine: str = "auto"
    window_title_pattern: str = ""
    # record in the application already open instead of launching it
    keep_session: bool = False
    # seconds before capture starts (time to reach the app and place the pointer)
    start_delay_s: float = Field(default=0, ge=0, le=120)


class ReplayRequest(BaseModel):
    execution_id: str
    definition: dict
    headless: bool = False
    engine: str = "auto"
    browser_path: str = ""
    inputs: dict = {}


_replay_tasks: dict[str, asyncio.Task] = {}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agent": "browser",
        "browser_path": BROWSER_PATH,
        "active_recordings": len(_recorders),
        "active_replays": sum(1 for r in _replays.values() if r["status"] == "running"),
    }


def _resolve_engine(body: StartRequest, effective_path: str) -> str:
    if body.keep_session:
        # only the desktop-hook recorder can attach to an application already running;
        # Playwright/Selenium always start their own browser
        return "subprocess"
    if body.engine == "auto":
        return "playwright" if _is_chromium_based(effective_path) else "selenium"
    return body.engine


async def _launch_recorder(body: StartRequest, effective_path: str, use_engine: str):
    """Create the recorder and start it (launching the application). Returns (recorder, engine)."""
    if body.keep_session:
        recorder = SubprocessRecorder(executable_path=effective_path, window_title_pattern=body.window_title_pattern)
        await recorder.start(body.target_url, keep_session=True)
        return recorder, "subprocess"
    recorder: BrowserRecorder | SeleniumRecorder | SubprocessRecorder
    if use_engine == "playwright":
        recorder = BrowserRecorder(executable_path=effective_path)
    elif use_engine == "subprocess":
        recorder = SubprocessRecorder(executable_path=effective_path, window_title_pattern=body.window_title_pattern)
    else:
        recorder = SeleniumRecorder(executable_path=effective_path)
    try:
        await recorder.start(body.target_url)
    except Exception as exc:
        if use_engine != "selenium":
            raise
        logger.warning("Selenium failed (%s), falling back to subprocess: %s", effective_path, exc)
        recorder = SubprocessRecorder(executable_path=effective_path, window_title_pattern=body.window_title_pattern)
        await recorder.start(body.target_url)
        use_engine = "subprocess"
    return recorder, use_engine


@app.post("/record/start")
async def start_recording(body: StartRequest):
    """With start_delay_s, nothing happens before the countdown ends — not even the
    application launch — so the user can get ready; the Studio polls /state."""
    session_id = str(uuid4())
    effective_path = body.browser_path or BROWSER_PATH
    use_engine = _resolve_engine(body, effective_path)
    delay = body.start_delay_s
    meta: dict = {
        "process_id": body.process_id, "target_url": body.target_url, "browser_path": effective_path,
        "action_type": body.action_type, "engine": use_engine, "keep_session": body.keep_session,
        "status": "countdown" if delay > 0 else "starting", "arm_at": time.time() + delay, "error": None,
    }
    _session_meta[session_id] = meta

    if delay <= 0:
        try:
            recorder, meta["engine"] = await _launch_recorder(body, effective_path, use_engine)
        except Exception as exc:
            _session_meta.pop(session_id, None)
            raise HTTPException(500, f"Recording start failed ({use_engine}): {exc}")
        _recorders[session_id] = recorder
        meta["status"] = "recording"
        logger.info("Recording started: %s (engine=%s)", session_id, meta["engine"])
        return {"session_id": session_id, "status": "recording", "engine": meta["engine"]}

    async def start_after_countdown() -> None:
        await asyncio.sleep(delay)
        meta["status"] = "starting"
        try:
            recorder, engine = await _launch_recorder(body, effective_path, use_engine)
        except Exception as exc:
            logger.exception("Recording start failed after countdown")
            meta["status"], meta["error"] = "failed", str(exc)
            return
        _recorders[session_id] = recorder
        meta["engine"], meta["status"] = engine, "recording"
        if not isinstance(recorder, SubprocessRecorder):
            _beep((880, 120), (880, 120))  # the desktop recorder beeps itself when armed
        logger.info("Recording started after %.0fs countdown: %s (engine=%s)", delay, session_id, engine)

    meta["task"] = asyncio.create_task(start_after_countdown())
    logger.info("Recording %s: starts in %.0fs", session_id, delay)
    return {"session_id": session_id, "status": "countdown", "engine": use_engine}


@app.get("/record/{session_id}/events")
async def get_events(session_id: str):
    recorder = _recorders.get(session_id)
    if not recorder:
        if session_id in _session_meta:
            return []  # still counting down
        raise HTTPException(404, "Session not found")
    events = await recorder.collect_events()
    return [_event_to_dict(e) for e in events]


@app.get("/record/{session_id}/state")
async def recording_state(session_id: str):
    """Countdown and Escape status, polled by the Studio (which then stops and saves)."""
    meta = _session_meta.get(session_id)
    recorder = _recorders.get(session_id)
    if not meta and not recorder:
        raise HTTPException(404, "Session not found")
    if not recorder:
        return {"armed": False, "remaining_s": max(0.0, round(meta["arm_at"] - time.time(), 1)),
                "stop_requested": False, "event_count": 0, "status": meta["status"], "error": meta.get("error")}
    if isinstance(recorder, SubprocessRecorder):
        return {**recorder.state(), "status": "recording", "error": None}
    return {"armed": True, "remaining_s": 0.0, "stop_requested": False, "event_count": len(recorder._events),
            "status": "recording", "error": None}


@app.get("/record/{session_id}/debug")
async def debug_recording(session_id: str):
    """Check script injection status and simulate a click for testing."""
    recorder = _recorders.get(session_id)
    if not recorder:
        raise HTTPException(404, "Session not found")
    if not recorder._page:
        raise HTTPException(500, "No active page (Selenium recorder — use /events)")
    try:
        status = await recorder._page.evaluate("""() => ({
            recording: !!window.__flowtix_recording,
            pushFn: typeof window.__flowtix_push,
            bufferLen: window.__flowtix_events ? window.__flowtix_events.length : -1,
            url: location.href,
        })""")
    except Exception as exc:
        status = {"error": str(exc)}

    return {"session_id": session_id, "capture_status": status, "python_events": len(recorder._events)}


@app.post("/record/{session_id}/test-click")
async def test_click(session_id: str):
    """Programmatically click the first link/button to verify event capture."""
    recorder = _recorders.get(session_id)
    if not recorder:
        raise HTTPException(404, "Session not found")
    if not recorder._page:
        raise HTTPException(500, "No active page (Selenium recorder)")

    before = len(recorder._events)
    try:
        await recorder._page.evaluate("""() => {
            const el = document.querySelector('a, button, input[type="submit"]');
            if (el) el.click();
            return el ? el.tagName + ' ' + (el.textContent || '').slice(0, 50) : 'no element found';
        }""")
    except Exception as exc:
        return {"error": str(exc)}

    await asyncio.sleep(0.5)
    after = len(recorder._events)
    return {"events_before": before, "events_after": after, "new_events": after - before}


@app.post("/record/{session_id}/stop")
async def stop_recording(session_id: str):
    recorder = _recorders.get(session_id)
    if not recorder:
        meta = _session_meta.get(session_id)
        if not meta:
            raise HTTPException(404, "Session not found")
        # stopped during the countdown: nothing was launched nor captured
        task = meta.pop("task", None)
        if task and not task.done():
            task.cancel()
        meta["status"] = "stopped"
        definition = transform_events([], process_name=meta.get("target_url", "Recorded"))
        return {"session_id": session_id, "status": "stopped", "event_count": 0, "definition": definition}

    events = await recorder.stop()
    meta = _session_meta.get(session_id, {})

    definition = transform_events(events, process_name=meta.get("target_url", "Recorded"))

    del _recorders[session_id]
    if session_id in _session_meta:
        _session_meta[session_id]["status"] = "stopped"

    logger.info("Recording stopped: %s — %d events, %d steps",
                session_id, len(events), len(definition.get("process", {}).get("steps", [])))

    return {
        "session_id": session_id,
        "status": "stopped",
        "event_count": len(events),
        "definition": definition,
    }


@app.post("/replay/start")
async def start_replay(body: ReplayRequest):
    replay_id = body.execution_id or str(uuid4())
    _replays[replay_id] = {"status": "running", "result": None}

    async def run():
        try:
            effective_path = body.browser_path or BROWSER_PATH
            use_engine = body.engine
            if use_engine == "auto":
                use_engine = "playwright" if _is_chromium_based(effective_path) else "subprocess"

            if use_engine == "subprocess":
                engine = SubprocessReplayEngine(executable_path=effective_path, slow_mo=50)
            else:
                engine = ReplayEngine(headless=body.headless, slow_mo=100, executable_path=effective_path)
            result = await engine.replay(body.definition, inputs=body.inputs)
            _replays[replay_id] = {
                "status": "succeeded" if result.success else "failed",
                "result": _replay_result_to_dict(result),
            }
        except asyncio.CancelledError:
            _replays[replay_id] = {"status": "failed", "result": {"error": "Annulé"}}
        except Exception as exc:
            logger.exception("Replay failed: %s", exc)
            _replays[replay_id] = {
                "status": "failed",
                "result": {"error": str(exc)},
            }

        finally:
            _replay_tasks.pop(replay_id, None)

    _replay_tasks[replay_id] = asyncio.create_task(run())
    return {"replay_id": replay_id, "status": "running"}


@app.post("/replay/{replay_id}/cancel")
async def cancel_replay(replay_id: str):
    task = _replay_tasks.get(replay_id)
    if task:
        request_stop()  # interrupts a mouse path / typing already running in a thread
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    return {"replay_id": replay_id, "cancelled": task is not None}


@app.get("/replay/{replay_id}/status")
async def get_replay_status(replay_id: str):
    info = _replays.get(replay_id)
    if not info:
        raise HTTPException(404, "Replay not found")
    return {"replay_id": replay_id, **info}


def _event_to_dict(e: RecordedEvent) -> dict:
    return {
        "timestamp": e.timestamp,
        "event_type": e.event_type,
        "url": e.url,
        "target": e.target,
        "value": e.value,
        "metadata": e.metadata,
    }


def _replay_result_to_dict(r: ReplayResult) -> dict:
    return {
        "success": r.success,
        "duration_ms": r.duration_ms,
        "steps": [
            {
                "step_id": s.step_id,
                "success": s.success,
                "duration_ms": s.duration_ms,
                "error": s.error,
            }
            for s in r.steps
        ],
    }
