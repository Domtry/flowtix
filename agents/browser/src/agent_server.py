"""Browser Agent — runs on the HOST machine, controls a real browser.

Exposes an HTTP API for:
- Recording sessions (Playwright for Chromium-based, Selenium for Firefox/others)
- Replaying process definitions
"""

import asyncio
import logging
import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .recorder import BrowserRecorder, RecordedEvent
from .selenium_recorder import SeleniumRecorder
from .subprocess_recorder import SubprocessRecorder
from .replay import ReplayEngine, ReplayResult
from .subprocess_replay import SubprocessReplayEngine
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


@app.post("/record/start")
async def start_recording(body: StartRequest):
    session_id = str(uuid4())
    effective_path = body.browser_path or BROWSER_PATH

    use_engine = body.engine
    if body.keep_session:
        # only the desktop-hook recorder can attach to an application already running;
        # Playwright/Selenium always start their own browser
        use_engine = "subprocess"
    elif use_engine == "auto":
        use_engine = "playwright" if _is_chromium_based(effective_path) else "selenium"

    if body.keep_session:
        recorder = SubprocessRecorder(executable_path=effective_path, window_title_pattern=body.window_title_pattern)
        try:
            await recorder.start(body.target_url, keep_session=True)
        except Exception as exc:
            raise HTTPException(500, f"Recording start failed: {exc}")
        _recorders[session_id] = recorder
        _session_meta[session_id] = {
            "process_id": body.process_id, "target_url": body.target_url, "browser_path": effective_path,
            "action_type": body.action_type, "engine": use_engine, "status": "recording", "keep_session": True,
        }
        logger.info("Recording started in the open session: %s", session_id)
        return {"session_id": session_id, "status": "recording", "engine": use_engine, "keep_session": True}

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
        if use_engine == "selenium":
            logger.warning("Selenium failed (%s), falling back to subprocess: %s", effective_path, exc)
            use_engine = "subprocess"
            recorder = SubprocessRecorder(executable_path=effective_path, window_title_pattern=body.window_title_pattern)
            try:
                await recorder.start(body.target_url)
            except Exception as exc2:
                raise HTTPException(500, f"Launch failed: {exc2}")
        else:
            raise HTTPException(500, f"Browser launch failed ({use_engine}): {exc}")

    _recorders[session_id] = recorder
    _session_meta[session_id] = {
        "process_id": body.process_id,
        "target_url": body.target_url,
        "browser_path": effective_path,
        "action_type": body.action_type,
        "engine": use_engine,
        "status": "recording",
    }
    logger.info("Recording started: %s -> %s (engine=%s, action=%s)",
                session_id, body.target_url, use_engine, body.action_type)
    return {"session_id": session_id, "status": "recording", "engine": use_engine}


@app.get("/record/{session_id}/events")
async def get_events(session_id: str):
    recorder = _recorders.get(session_id)
    if not recorder:
        raise HTTPException(404, "Session not found")
    events = await recorder.collect_events()
    return [_event_to_dict(e) for e in events]


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
        raise HTTPException(404, "Session not found")

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
