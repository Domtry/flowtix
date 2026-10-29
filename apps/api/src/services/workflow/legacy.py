"""One-time conversion of pre-workflow pipelines (file -> robot) into graphs."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.pipeline import Pipeline, PipelineFile
from ...models.process import Process

logger = logging.getLogger(__name__)


def _node(type_: str, name: str, x: int, y: int, config: dict | None = None) -> dict:
    return {"id": f"n{uuid.uuid4().hex[:8]}", "type": type_, "name": name,
            "position": {"x": x, "y": y}, "config": config or {}}


def _edge(src: dict, tgt: dict, src_port: str = "main") -> dict:
    return {"id": f"e{uuid.uuid4().hex[:8]}", "source": src["id"], "source_port": src_port,
            "target": tgt["id"], "target_port": "main"}


def build_legacy_graph(p: Pipeline, file_id: str | None) -> dict:
    nodes, edges = [], []
    triggers = [_node("trigger.manual", "Lancement manuel", 60, 80)]
    if p.schedule_cron:
        triggers.append(_node("trigger.schedule", "Planifié", 60, 220,
                              {"cron": p.schedule_cron, "enabled": bool(p.schedule_enabled)}))
    webhook = None
    if p.source_type == "api" or p.api_key_hash:
        webhook = _node("trigger.webhook", "Appel API", 60, 360)
    robot = _node("robot.run", "Exécuter le robot", 640, 180, {
        "process_id": str(p.process_id) if p.process_id else None,
        "version_id": str(p.version_id) if p.version_id else None,
        "mapping": {step: "{{" + col + "}}" for step, col in (p.mapping or {}).items() if col},
    })
    nodes += triggers
    if file_id:
        reader = _node("data.read_file", "Lire le fichier", 340, 120,
                       {"file_id": file_id, "sheet": p.source_sheet})
        nodes.append(reader)
        edges += [_edge(t, reader) for t in triggers]
        edges.append(_edge(reader, robot))
    else:
        edges += [_edge(t, robot) for t in triggers]
    if webhook:
        nodes.append(webhook)
        edges.append(_edge(webhook, robot))
    nodes.append(robot)
    return with_end_node({"nodes": nodes, "edges": edges})


async def convert_legacy_pipelines(db: AsyncSession) -> None:
    result = await db.execute(select(Pipeline).where(Pipeline.graph.is_(None)))
    for p in result.scalars().all():
        file_id = None
        if p.source_file and p.source_filename:
            f = PipelineFile(pipeline_id=p.id, kind="source", filename=p.source_filename, content=p.source_file)
            db.add(f)
            await db.flush()
            file_id = str(f.id)
        p.graph = build_legacy_graph(p, file_id)
        logger.info("Pipeline %s converted to a workflow (%d nodes)", p.id, len(p.graph["nodes"]))
    await db.commit()
    await assign_workflow_robots(db)
    await add_missing_ends(db)


_PRIMARY_PORTS = ("success", "main", "done", "true", "kept", "default")


def with_end_node(graph: dict) -> dict:
    """Add a success "Fin" closing every branch that leads nowhere."""
    from .catalog import NODE_TYPES, output_ports

    nodes, edges = list(graph.get("nodes", [])), list(graph.get("edges", []))
    with_outgoing = {e["source"] for e in edges}
    dangling = [n for n in nodes if n.get("type") in NODE_TYPES and n["id"] not in with_outgoing
                and output_ports(n)]
    xs = [n.get("position", {}).get("x", 0) for n in nodes] or [0]
    ys = [n.get("position", {}).get("y", 0) for n in dangling or nodes] or [160]
    end = _node("flow.end", "Fin", max(xs) + 320, int(sum(ys) / len(ys)), {"result": "success", "message": ""})
    nodes.append(end)
    for n in dangling:
        ports = output_ports(n)
        port = next((p for p in _PRIMARY_PORTS if p in ports), ports[0])
        edges.append(_edge(n, end, port))
    return {"nodes": nodes, "edges": edges}


async def add_missing_ends(db: AsyncSession) -> None:
    """Workflows created before the closing point existed get one."""
    for p in (await db.execute(select(Pipeline))).scalars().all():
        graph = p.graph or {}
        if graph.get("nodes") and not any(n.get("type") == "flow.end" for n in graph["nodes"]):
            p.graph = with_end_node(graph)
            logger.info("Workflow %s: closing point added", p.id)
    await db.commit()


async def assign_workflow_robots(db: AsyncSession) -> None:
    """Workflows created before the workflow-level robot: take the robot of their
    processes when they all share one."""
    result = await db.execute(select(Pipeline).where(Pipeline.robot_code.is_(None)))
    for p in result.scalars().all():
        ids = {(n.get("config") or {}).get("process_id")
               for n in (p.graph or {}).get("nodes", []) if n.get("type") == "robot.run"} - {None, ""}
        robots = set()
        for pid in ids:
            try:
                proc = await db.get(Process, uuid.UUID(str(pid)))
            except ValueError:
                proc = None
            if proc and proc.robot_code:
                robots.add(proc.robot_code)
        if len(robots) == 1:
            p.robot_code = robots.pop()
            logger.info("Workflow %s: robot set to %s", p.id, p.robot_code)
    await db.commit()
