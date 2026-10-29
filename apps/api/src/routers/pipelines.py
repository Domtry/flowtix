"""Workflows ("pipelines"): graphs of triggers, robots, logic and data nodes."""

import base64
import csv
import hashlib
import hmac
import io
import secrets
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.pipeline import Pipeline, PipelineFile, PipelineRun, PipelineRunItem
from ..models.process import AppModule, Process
from ..services import cron
from ..services.execution_service import ExecutionService
from ..services.pipeline_runner import has_active_run, resolve_version, runner
from ..services.pipeline_source import MAX_ROWS, SourceError, excel_sheets, parse_source
from ..services.workflow.catalog import TRIGGERS, validate

router = APIRouter(tags=["pipelines"])

MAX_FILE_BYTES = 10 * 1024 * 1024
PREVIEW_ROWS = 10


# ---------------------------------------------------------------- schemas

class PipelineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    robot_code: str | None = Field(default=None, max_length=100)


class PipelineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    robot_code: str | None = Field(default=None, max_length=100)
    graph: dict | None = None


class FileUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str


class RunRequest(BaseModel):
    rows: list[dict] | None = None


# ---------------------------------------------------------------- helpers

def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _new_graph() -> dict:
    """A new workflow starts as Début -> Fin; blocks are inserted in between."""
    start = {"id": f"n{uuid_mod.uuid4().hex[:8]}", "type": "trigger.manual",
             "name": "Début", "position": {"x": 80, "y": 160}, "config": {}}
    end = {"id": f"n{uuid_mod.uuid4().hex[:8]}", "type": "flow.end", "name": "Fin",
           "position": {"x": 700, "y": 160}, "config": {"result": "success", "message": ""}}
    edge = {"id": f"e{uuid_mod.uuid4().hex[:8]}", "source": start["id"], "source_port": "main",
            "target": end["id"], "target_port": "main"}
    return {"nodes": [start, end], "edges": [edge]}


async def _get_pipeline(db: AsyncSession, pipeline_id: UUID) -> Pipeline:
    p = await db.get(Pipeline, pipeline_id)
    if not p:
        raise HTTPException(404, "Workflow introuvable")
    return p


def _nodes(p: Pipeline, type_: str | None = None) -> list[dict]:
    nodes = (p.graph or {}).get("nodes", [])
    return [n for n in nodes if type_ is None or n.get("type") == type_]


def _next_run(p: Pipeline) -> str | None:
    now, best = datetime.now(timezone.utc), None
    for n in _nodes(p, "trigger.schedule"):
        cfg = n.get("config") or {}
        if not (cfg.get("enabled") and cfg.get("cron")):
            continue
        try:
            nxt = cron.next_run(cfg["cron"], now)
        except ValueError:
            continue
        if nxt and (best is None or nxt < best):
            best = nxt
    return _iso(best)


def _run_dict(run: PipelineRun) -> dict:
    return {
        "id": str(run.id), "pipeline_id": str(run.pipeline_id), "trigger": run.trigger,
        "status": run.status, "total_rows": run.total_rows, "succeeded": run.succeeded,
        "failed": run.failed, "error": run.error, "start_node_id": run.start_node_id,
        "started_at": _iso(run.started_at), "completed_at": _iso(run.completed_at),
        "created_at": _iso(run.created_at),
    }


async def _process_robots(db: AsyncSession) -> dict[str, str | None]:
    rows = await db.execute(select(Process.id, Process.robot_code))
    return {str(pid): code for pid, code in rows.all()}


async def _check_robot(db: AsyncSession, code: str) -> AppModule:
    robot = (await db.execute(select(AppModule).where(AppModule.code == code))).scalar_one_or_none()
    if not robot:
        raise HTTPException(404, f"Robot introuvable : {code}")
    return robot


async def _issues(db: AsyncSession, p: Pipeline) -> list[dict]:
    return validate(p.graph or {}, p.robot_code, await _process_robots(db))


async def _pipeline_dict(db: AsyncSession, p: Pipeline, detail: bool = False) -> dict:
    robot = None
    if p.robot_code:
        robot = (await db.execute(select(AppModule).where(AppModule.code == p.robot_code))).scalar_one_or_none()
    last = (await db.execute(
        select(PipelineRun).where(PipelineRun.pipeline_id == p.id)
        .order_by(PipelineRun.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    d = {
        "id": str(p.id), "name": p.name, "description": p.description,
        "robot_code": p.robot_code, "robot_name": robot.name if robot else None,
        "triggers": sorted({n["type"] for n in _nodes(p) if n.get("type") in TRIGGERS}),
        "node_count": len(_nodes(p)), "next_run_at": _next_run(p),
        "has_api_key": bool(p.api_key_hash), "last_run": _run_dict(last) if last else None,
        "created_at": _iso(p.created_at), "updated_at": _iso(p.updated_at),
    }
    if detail:
        d["graph"] = p.graph or _new_graph()
        d["issues"] = validate(d["graph"], p.robot_code, await _process_robots(db))
    return d


def _file_meta(f: PipelineFile, sheet: str | None = None, preview: bool = False) -> dict:
    d: dict = {"id": str(f.id), "filename": f.filename, "kind": f.kind,
               "run_id": str(f.run_id) if f.run_id else None, "size": len(f.content or b""),
               "created_at": _iso(f.created_at)}
    if f.kind == "source":
        if f.filename.lower().endswith((".xlsx", ".xls", ".xlsm")):
            d["sheets"] = excel_sheets(f.content)
        try:
            columns, rows = parse_source(f.filename, f.content, sheet)
            d.update(columns=columns, row_count=len(rows))
            if preview:
                d["preview"] = rows[:PREVIEW_ROWS]
        except SourceError as exc:
            d["error"] = str(exc)
    return d


def _normalize_rows(rows: list) -> list[dict]:
    if len(rows) > MAX_ROWS:
        raise HTTPException(400, f"Trop d'éléments ({len(rows)}), maximum {MAX_ROWS}")
    if not all(isinstance(r, dict) for r in rows):
        raise HTTPException(400, "Chaque élément doit être un objet JSON")
    return rows


async def _start(db: AsyncSession, p: Pipeline, trigger: str, node_type: str, items: list[dict]) -> dict:
    issues = await _issues(db, p)
    if issues:
        raise HTTPException(400, "Workflow incomplet : " + " ; ".join(i["message"] for i in issues[:5]))
    starts = _nodes(p, node_type)
    if not starts:
        label = {"trigger.manual": "manuel", "trigger.webhook": "« Appel API »"}[node_type]
        raise HTTPException(400, f"Ajoutez un déclencheur {label} au workflow")
    if await has_active_run(db, p.id):
        raise HTTPException(409, "Un run de ce workflow est déjà en cours ou en attente")
    run = await runner.create_run(db, p, trigger, starts[0]["id"], items)
    return _run_dict(run)


# ---------------------------------------------------------------- CRUD

@router.get("/pipelines")
async def list_pipelines(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(select(Pipeline).order_by(Pipeline.created_at.desc()))
    return [await _pipeline_dict(db, p) for p in result.scalars().all()]


@router.post("/pipelines", status_code=201)
async def create_pipeline(body: PipelineCreate, db: AsyncSession = Depends(get_db)) -> dict:
    if body.robot_code:
        await _check_robot(db, body.robot_code)
    p = Pipeline(name=body.name, description=body.description, graph=_new_graph(), source_type="workflow",
                 robot_code=body.robot_code or None)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return await _pipeline_dict(db, p, detail=True)


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    return await _pipeline_dict(db, await _get_pipeline(db, pipeline_id), detail=True)


@router.put("/pipelines/{pipeline_id}")
async def update_pipeline(pipeline_id: UUID, body: PipelineUpdate, db: AsyncSession = Depends(get_db)) -> dict:
    """Saves even an incomplete graph (work in progress); `issues` says what blocks a run."""
    p = await _get_pipeline(db, pipeline_id)
    if body.name is not None:
        p.name = body.name
    if body.description is not None:
        p.description = body.description
    if body.robot_code is not None:
        if body.robot_code:
            await _check_robot(db, body.robot_code)
        p.robot_code = body.robot_code or None
    if body.graph is not None:
        nodes, edges = body.graph.get("nodes"), body.graph.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise HTTPException(400, "Graphe invalide : nodes et edges attendus")
        p.graph = {"nodes": nodes, "edges": edges}
    await db.commit()
    await db.refresh(p)
    return await _pipeline_dict(db, p, detail=True)


@router.delete("/pipelines/{pipeline_id}", status_code=204)
async def delete_pipeline(pipeline_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    p = await _get_pipeline(db, pipeline_id)
    if await has_active_run(db, p.id):
        raise HTTPException(409, "Annulez le run en cours avant de supprimer le workflow")
    # explicit order: items/files -> runs -> workflow (no ORM relationships to sort it for us)
    run_ids = select(PipelineRun.id).where(PipelineRun.pipeline_id == p.id)
    await db.execute(delete(PipelineRunItem).where(PipelineRunItem.run_id.in_(run_ids)))
    await db.execute(delete(PipelineFile).where(PipelineFile.pipeline_id == p.id))
    await db.execute(delete(PipelineRun).where(PipelineRun.pipeline_id == p.id))
    await db.delete(p)
    await db.commit()


# ---------------------------------------------------------------- files

@router.get("/pipelines/{pipeline_id}/files")
async def list_files(pipeline_id: UUID, kind: str = "source", db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(
        select(PipelineFile).where(PipelineFile.pipeline_id == pipeline_id, PipelineFile.kind == kind)
        .order_by(PipelineFile.created_at.desc()))
    return [_file_meta(f) for f in result.scalars().all()]


@router.post("/pipelines/{pipeline_id}/files", status_code=201)
async def upload_file(pipeline_id: UUID, body: FileUpload, db: AsyncSession = Depends(get_db)) -> dict:
    await _get_pipeline(db, pipeline_id)
    try:
        content = base64.b64decode(body.content_base64, validate=True)
    except Exception as exc:
        raise HTTPException(400, "Contenu du fichier invalide") from exc
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(400, "Fichier trop volumineux (10 Mo maximum)")
    try:
        parse_source(body.filename, content)
    except SourceError as exc:
        raise HTTPException(400, str(exc)) from exc
    f = PipelineFile(pipeline_id=pipeline_id, kind="source", filename=body.filename, content=content)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return _file_meta(f, preview=True)


async def _get_file(db: AsyncSession, file_id: UUID) -> PipelineFile:
    f = await db.get(PipelineFile, file_id)
    if not f:
        raise HTTPException(404, "Fichier introuvable")
    return f


@router.get("/pipeline-files/{file_id}")
async def file_preview(file_id: UUID, sheet: str | None = None, db: AsyncSession = Depends(get_db)) -> dict:
    return _file_meta(await _get_file(db, file_id), sheet=sheet, preview=True)


@router.get("/pipeline-files/{file_id}/download")
async def download_file(file_id: UUID, db: AsyncSession = Depends(get_db)) -> Response:
    f = await _get_file(db, file_id)
    media = "text/csv" if f.filename.lower().endswith(".csv") else "application/octet-stream"
    return Response(content=f.content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{f.filename}"'})


@router.delete("/pipeline-files/{file_id}", status_code=204)
async def delete_file(file_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    f = await _get_file(db, file_id)
    p = await db.get(Pipeline, f.pipeline_id)
    used = [n.get("name") for n in _nodes(p) if (n.get("config") or {}).get("file_id") == str(f.id)] if p else []
    if used:
        raise HTTPException(409, f"Fichier utilisé par : {', '.join(used)}")
    await db.delete(f)
    await db.commit()


# ---------------------------------------------------------------- robot node helper

@router.get("/workflow/robot-fields")
async def robot_fields(process_id: UUID, version_id: UUID | None = None,
                       db: AsyncSession = Depends(get_db)) -> list[dict]:
    """The recorded text inputs of a process: what a robot node can fill from the data."""
    if not await db.get(Process, process_id):
        raise HTTPException(404, "Processus introuvable")
    version = await resolve_version(db, process_id, version_id)
    if not version:
        return []
    steps = version.definition.get("process", version.definition).get("steps", [])
    fields, last_click = [], ""
    for i, s in enumerate(steps):
        if s.get("type") in ("ui.click", "ui.dblclick"):
            last_click = (s.get("target") or {}).get("text") or s.get("label") or ""
        if s.get("type") != "ui.fill":
            continue
        value = str(s.get("value") or "")
        shown = value if value.startswith("${") else (
            value[:2] + "•" * (len(value) - 2) if len(value) > 2 else "•" * len(value))
        window = (s.get("metadata") or {}).get("window_title", "")
        fields.append({
            "step_id": s.get("id"), "index": i + 1, "recorded_value": shown, "window_title": window,
            # a click on the window itself carries the window title as its "text"
            "after_click": "" if last_click and last_click in window else last_click[:80],
        })
    return fields


_STEP_KIND = {"browser.navigate": "Ouverture de l'application", "browser.wait": "Attente du chargement",
              "ui.click": "Clic", "ui.dblclick": "Double-clic", "ui.fill": "Saisie",
              "keyboard.press": "Touche", "ui.hover": "Survol", "ui.scroll": "Défilement"}


@router.get("/workflow/process-steps")
async def process_steps(process_id: UUID, version_id: UUID | None = None,
                        db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Steps of a process, to choose where a process continues an open session.
    Typed values are never returned (they may be passwords)."""
    if not await db.get(Process, process_id):
        raise HTTPException(404, "Processus introuvable")
    version = await resolve_version(db, process_id, version_id)
    if not version:
        return []
    out = []
    for i, s in enumerate(version.definition.get("process", version.definition).get("steps", [])):
        t = s.get("type", "")
        kind = _STEP_KIND.get(t, t)
        if t in ("ui.click", "ui.dblclick", "ui.hover"):
            detail = (s.get("target") or {}).get("text") or ""
        elif t == "keyboard.press":
            detail = (s.get("params") or {}).get("key", "")
        elif t == "ui.fill":
            detail = f"{len(str(s.get('value') or ''))} caractère(s)"
        elif t == "browser.navigate":
            detail = (s.get("params") or {}).get("url", "")
        else:
            detail = ""
        window = (s.get("metadata") or {}).get("window_title", "")
        out.append({"step_id": s.get("id"), "index": i + 1, "type": t,
                    "label": f"{kind}{' « ' + detail[:60] + ' »' if detail else ''}", "window_title": window[:80]})
    return out


# ---------------------------------------------------------------- runs

@router.post("/pipelines/{pipeline_id}/run")
async def run_pipeline(pipeline_id: UUID, body: RunRequest | None = None,
                       db: AsyncSession = Depends(get_db)) -> dict:
    p = await _get_pipeline(db, pipeline_id)
    items = _normalize_rows(body.rows) if body and body.rows else [{}]
    return await _start(db, p, "manual", "trigger.manual", items)


@router.get("/pipelines/{pipeline_id}/runs")
async def list_runs(pipeline_id: UUID, db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.pipeline_id == pipeline_id)
        .order_by(PipelineRun.created_at.desc()).limit(50))
    return [_run_dict(r) for r in result.scalars().all()]


@router.get("/pipeline-runs/{run_id}")
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(404, "Run introuvable")
    items = (await db.execute(
        select(PipelineRunItem).where(PipelineRunItem.run_id == run.id).order_by(PipelineRunItem.row_index)
    )).scalars().all()
    files = (await db.execute(
        select(PipelineFile).where(PipelineFile.run_id == run.id).order_by(PipelineFile.created_at)
    )).scalars().all()
    d = _run_dict(run)
    d["node_results"] = run.node_results or {}
    d["files"] = [_file_meta(f) for f in files]
    d["items"] = [{
        "id": str(i.id), "node_id": i.node_id, "row_index": i.row_index, "row_data": i.row_data,
        "status": i.status, "execution_id": str(i.execution_id) if i.execution_id else None,
        "error": i.error, "started_at": _iso(i.started_at), "completed_at": _iso(i.completed_at),
    } for i in items]
    return d


@router.post("/pipeline-runs/{run_id}/cancel")
async def cancel_run(run_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(404, "Run introuvable")
    if run.status == "queued":
        run.status, run.completed_at = "cancelled", datetime.now(timezone.utc)
        await db.commit()
        return _run_dict(run)
    if run.status != "running":
        raise HTTPException(400, f"Le run est déjà {run.status}")
    run.status = "cancelling"
    current = (await db.execute(
        select(PipelineRunItem).where(PipelineRunItem.run_id == run.id, PipelineRunItem.status == "running")
    )).scalar_one_or_none()
    await db.commit()
    if current and current.execution_id:
        await ExecutionService().cancel_execution(str(current.execution_id))
    return _run_dict(run)


@router.post("/pipeline-runs/{run_id}/retry-failed")
async def retry_failed(run_id: UUID, node_id: str | None = None, db: AsyncSession = Depends(get_db)) -> dict:
    """Re-run a robot node on its failed items only; the workflow continues from there."""
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(404, "Run introuvable")
    query = select(PipelineRunItem).where(
        PipelineRunItem.run_id == run.id, PipelineRunItem.status.in_(("failed", "skipped")),
        PipelineRunItem.node_id.is_not(None))
    if node_id:
        query = query.where(PipelineRunItem.node_id == node_id)
    failed = (await db.execute(query.order_by(PipelineRunItem.row_index))).scalars().all()
    if not failed:
        raise HTTPException(400, "Aucun élément en échec à relancer")
    target = node_id or failed[0].node_id
    p = await _get_pipeline(db, run.pipeline_id)
    if not any(n["id"] == target for n in _nodes(p)):
        raise HTTPException(400, "Le bloc robot de ces éléments n'existe plus dans le workflow")
    if await has_active_run(db, p.id):
        raise HTTPException(409, "Un run de ce workflow est déjà en cours ou en attente")
    items = [i.row_data for i in failed if i.node_id == target]
    new_run = await runner.create_run(db, p, "retry", target, items)
    return _run_dict(new_run)


@router.get("/pipeline-runs/{run_id}/report.csv")
async def run_report(run_id: UUID, db: AsyncSession = Depends(get_db)) -> Response:
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(404, "Run introuvable")
    p = await db.get(Pipeline, run.pipeline_id)
    names = {n["id"]: n.get("name") or n["type"] for n in _nodes(p)} if p else {}
    items = (await db.execute(
        select(PipelineRunItem).where(PipelineRunItem.run_id == run.id).order_by(PipelineRunItem.row_index)
    )).scalars().all()
    columns: list[str] = []
    for i in items:
        columns += [c for c in i.row_data if c not in columns and not c.startswith("_")]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")  # ';' so French Excel opens it in columns
    w.writerow(["n°", "robot", *columns, "statut", "erreur", "execution_id"])
    for i in items:
        w.writerow([i.row_index + 1, names.get(i.node_id or "", ""), *[i.row_data.get(c, "") for c in columns],
                    i.status, i.error or "", str(i.execution_id or "")])
    return Response(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="workflow-run-{run_id}.csv"'})


# ---------------------------------------------------------------- external trigger

@router.post("/pipelines/{pipeline_id}/api-key")
async def regenerate_api_key(pipeline_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Returns the key once; only its hash is stored."""
    p = await _get_pipeline(db, pipeline_id)
    key = "ftx_" + secrets.token_urlsafe(32)
    p.api_key_hash = _hash_key(key)
    await db.commit()
    return {"api_key": key}


async def _authorized(db: AsyncSession, pipeline_id: UUID, key: str | None) -> Pipeline:
    p = await db.get(Pipeline, pipeline_id)
    # same answer for unknown workflow and bad key: don't reveal which workflows exist
    if not p or not p.api_key_hash or not key or not hmac.compare_digest(_hash_key(key), p.api_key_hash):
        raise HTTPException(401, "Clé API invalide")
    return p


@router.post("/pipelines/{pipeline_id}/trigger")
async def trigger_pipeline(
    pipeline_id: UUID, body: Any = Body(default=None),
    x_api_key: str | None = Header(default=None), db: AsyncSession = Depends(get_db),
) -> dict:
    """Body: {"rows": [...]} -> one item per row; a list -> one item per element;
    any other object -> a single item; empty -> one empty item."""
    p = await _authorized(db, pipeline_id, x_api_key)
    if isinstance(body, dict) and isinstance(body.get("rows"), list):
        items = _normalize_rows(body["rows"])
    elif isinstance(body, list):
        items = _normalize_rows(body)
    elif isinstance(body, dict) and body:
        items = [body]
    else:
        items = [{}]
    return await _start(db, p, "api", "trigger.webhook", items)


@router.get("/pipelines/{pipeline_id}/trigger/{run_id}")
async def trigger_status(
    pipeline_id: UUID, run_id: UUID,
    x_api_key: str | None = Header(default=None), db: AsyncSession = Depends(get_db),
) -> dict:
    p = await _authorized(db, pipeline_id, x_api_key)
    run = await db.get(PipelineRun, run_id)
    if not run or run.pipeline_id != p.id:
        raise HTTPException(404, "Run introuvable")
    return await get_run(run_id, db)
