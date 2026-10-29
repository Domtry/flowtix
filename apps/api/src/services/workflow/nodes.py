"""What each node does with its items. Persistence and side effects that need the
database or the desktop (robot runs, files, SMTP settings) go through `ctx`,
implemented by the pipeline runner."""

import asyncio
import copy
import csv
import io
import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import httpx

from .engine import NodeError
from .expressions import evaluate, matches, render

OLLAMA_URL = os.environ.get("FLOWTIX_OLLAMA_URL", "http://host.docker.internal:11434")
HTTP_TIMEOUT = 30.0
AI_TIMEOUT = 180.0
MAX_WAIT_S = 3600


# ------------------------------------------------------------------ triggers

async def passthrough(node: dict, items: list, ctx: Any) -> dict:
    return {"main": items}


# ------------------------------------------------------------------- robot

async def robot_run(node: dict, items: list, ctx: Any) -> dict:
    """Run the recorded process once per item, mapped fields typed from the item."""
    cfg = node.get("config") or {}
    mapping = cfg.get("mapping") or {}
    success, failed = [], []
    for item in items:
        await ctx.check_cancel()
        values = {step_id: render(tpl, item) for step_id, tpl in mapping.items() if tpl}
        session = {"keep": bool(cfg.get("keep_session")), "start_step_id": cfg.get("start_step_id") or None}
        ok, error, execution_id = await ctx.run_robot(node, cfg.get("process_id"), cfg.get("version_id"),
                                                      values, item, session)
        out = {**item, "_execution_id": execution_id}
        if ok:
            success.append(out)
        else:
            failed.append({**out, "_erreur": error})
    return {"success": success, "error": failed}


def apply_values(definition: dict, values: dict) -> dict:
    d = copy.deepcopy(definition)
    for step in d.get("process", d).get("steps", []):
        if step.get("id") in values:
            step["value"] = values[step["id"]]
    return d


LAUNCH_STEPS = {"browser.navigate", "browser.wait"}


def keep_session(definition: dict, start_step_id: str | None) -> dict:
    """Continue in the application already open: drop the steps before the chosen
    step, or by default the opening steps (launching the app, waiting for it)."""
    d = copy.deepcopy(definition)
    proc = d.get("process", d)
    steps = proc.get("steps", [])
    if start_step_id:
        index = next((i for i, s in enumerate(steps) if s.get("id") == start_step_id), None)
        if index is None:
            raise NodeError("L'étape de reprise n'existe plus dans ce processus : choisissez-la à nouveau")
        proc["steps"] = steps[index:]
    else:
        first = next((i for i, s in enumerate(steps) if s.get("type") not in LAUNCH_STEPS), len(steps))
        proc["steps"] = steps[first:]
    if proc["steps"]:
        # no previous click in this run to start the recorded pointer path from
        (proc["steps"][0].setdefault("metadata", {}) or {}).pop("path_from_prev", None)
    return d


# ------------------------------------------------------------------- logic

async def logic_if(node: dict, items: list, ctx: Any) -> dict:
    cfg = node.get("config") or {}
    yes, no = [], []
    for item in items:
        (yes if matches(cfg, item) else no).append(item)
    return {"true": yes, "false": no}


async def logic_switch(node: dict, items: list, ctx: Any) -> dict:
    """One output per case (first matching case wins), "default" for the rest."""
    cfg = node.get("config") or {}
    cases = cfg.get("cases") or []
    out: dict[str, list] = {c["id"]: [] for c in cases}
    out["default"] = []
    for item in items:
        for c in cases:
            rule = {"field": cfg.get("field", ""), "op": cfg.get("op", "equals"), "value": c.get("value", "")}
            if evaluate(rule, item):
                out[c["id"]].append(item)
                break
        else:
            out["default"].append(item)
    return out


async def logic_wait(node: dict, items: list, ctx: Any) -> dict:
    seconds = min(float((node.get("config") or {}).get("seconds", 0) or 0), MAX_WAIT_S)
    while seconds > 0:
        await ctx.check_cancel()
        step = min(1.0, seconds)
        await asyncio.sleep(step)
        seconds -= step
    return {"main": items}


# -------------------------------------------------------------------- data

async def data_read_file(node: dict, items: list, ctx: Any) -> dict:
    cfg = node.get("config") or {}
    return {"main": await ctx.read_file(cfg.get("file_id"), cfg.get("sheet"))}


async def data_filter(node: dict, items: list, ctx: Any) -> dict:
    out = await logic_if(node, items, ctx)
    return {"kept": out["true"], "rejected": out["false"]}


_CASES = {"upper": str.upper, "lower": str.lower, "trim": str.strip,
          "capitalize": lambda s: s.strip().title()}


def set_fields(cfg: dict, item: dict) -> dict:
    """Operations, in order: set a field from a template (with optional case), rename,
    remove; then optionally keep only the listed fields."""
    out = dict(item)
    for op in cfg.get("operations") or []:
        kind, field = op.get("op", "set"), (op.get("field") or "").strip()
        if not field:
            continue
        if kind == "set":
            value = render(op.get("value", ""), out)
            fn = _CASES.get(op.get("case") or "")
            out[field] = fn(value) if fn else value
        elif kind == "rename":
            to = (op.get("to") or "").strip()
            if to and field in out:
                out[to] = out.pop(field)
        elif kind == "remove":
            out.pop(field, None)
    keep = [f.strip() for f in (cfg.get("keep_only") or "").split(",") if f.strip()]
    if keep:
        out = {k: out.get(k, "") for k in keep}
    return out


async def data_set(node: dict, items: list, ctx: Any) -> dict:
    cfg = node.get("config") or {}
    return {"main": [set_fields(cfg, i) for i in items]}


def to_file(items: list, fmt: str) -> bytes:
    columns: list[str] = []
    for i in items:
        columns += [c for c in i if c not in columns]
    rows = [[_cell(i.get(c)) for c in columns] for i in items]
    if fmt == "xlsx":
        import pandas as pd
        buf = io.BytesIO()
        pd.DataFrame(rows, columns=columns).to_excel(buf, index=False)
        return buf.getvalue()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")  # ';' so French Excel opens it in columns
    w.writerow(columns)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def _cell(v: Any) -> Any:
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else ("" if v is None else v)


async def data_write_file(node: dict, items: list, ctx: Any) -> dict:
    cfg = node.get("config") or {}
    fmt = "xlsx" if cfg.get("format") == "xlsx" else "csv"
    name = re.sub(r"[\\/:*?\"<>|]", "_", (cfg.get("filename") or "resultat").strip())
    if not name.lower().endswith("." + fmt):
        name += "." + fmt
    await ctx.save_output_file(name, to_file(items, fmt))
    return {"main": items}


# -------------------------------------------------------------------- http

async def http_request(node: dict, items: list, ctx: Any) -> dict:
    cfg = node.get("config") or {}
    method = cfg.get("method", "GET")
    field = (cfg.get("response_field") or "reponse").strip()
    targets = items if cfg.get("per_item", True) else items[:1] or [{}]
    success, failed = [], []
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        for item in targets:
            await ctx.check_cancel()
            url = render(cfg.get("url", ""), item).strip()
            headers = {render(h.get("key", ""), item): render(h.get("value", ""), item)
                       for h in cfg.get("headers") or [] if h.get("key")}
            body = render(cfg.get("body", ""), item) if method in ("POST", "PUT", "PATCH") else None
            if body and "content-type" not in {k.lower() for k in headers}:
                headers["Content-Type"] = "application/json" if body.lstrip()[:1] in "{[" else "text/plain"
            try:
                resp = await client.request(method, url, headers=headers,
                                            content=body.encode() if body else None)
            except httpx.HTTPError as exc:
                failed.append({**item, "_erreur": f"{exc.__class__.__name__}: {exc}"})
                continue
            try:
                data: Any = resp.json()
            except ValueError:
                data = resp.text
            out = {**item, field: data, "_http_status": resp.status_code}
            if resp.is_success:
                success.append(out)
            else:
                failed.append({**out, "_erreur": f"HTTP {resp.status_code}"})
    return {"success": success, "error": failed}


# ------------------------------------------------------------------- email

def _send_mail(smtp: dict, recipients: list[str], subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = smtp["sender"]
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    security = smtp.get("security", "starttls")
    context = ssl.create_default_context()
    if security == "ssl":
        server: smtplib.SMTP = smtplib.SMTP_SSL(smtp["host"], int(smtp["port"]), timeout=30, context=context)
    else:
        server = smtplib.SMTP(smtp["host"], int(smtp["port"]), timeout=30)
    with server:
        if security == "starttls":
            server.starttls(context=context)
        if smtp.get("username"):
            server.login(smtp["username"], smtp.get("password", ""))
        server.send_message(msg)


async def email_send(node: dict, items: list, ctx: Any) -> dict:
    cfg = node.get("config") or {}
    smtp = await ctx.smtp_settings()
    if not smtp:
        raise NodeError("Serveur e-mail non configuré : renseignez-le dans Settings")
    batches = [(item, {}) for item in items] if cfg.get("mode") == "per_item" else \
        [(items[0] if items else {}, {"nombre": len(items)})]
    for item, extra in batches:
        recipients = [r.strip() for r in re.split(r"[;,]", render(cfg.get("to", ""), item, extra)) if r.strip()]
        if not recipients:
            raise NodeError("Aucun destinataire après remplacement des champs")
        subject = render(cfg.get("subject", ""), item, extra)
        body = render(cfg.get("body", ""), item, extra)
        await asyncio.get_running_loop().run_in_executor(None, _send_mail, smtp, recipients, subject, body)
    return {"main": items}


# ---------------------------------------------------------------------- AI

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


async def ai_prompt(node: dict, items: list, ctx: Any) -> dict:
    cfg = node.get("config") or {}
    field = cfg["output_field"].strip()
    want_json = bool(cfg.get("json"))
    timeout_s = float(cfg.get("timeout_s") or AI_TIMEOUT)
    out = []
    async with httpx.AsyncClient(timeout=None) as client:
        for item in items:
            await ctx.check_cancel()
            payload: dict = {
                "model": cfg["model"], "prompt": render(cfg["prompt"], item), "stream": False,
                # reasoning models (qwen3, deepseek-r1) otherwise "think" for thousands of
                # tokens first — minutes per item on a CPU
                "think": bool(cfg.get("think", False)),
                "options": {"temperature": float(cfg.get("temperature", 0.1)),
                            "num_predict": int(cfg.get("max_tokens") or 256)},
            }
            if want_json:
                payload["format"] = "json"
            try:
                # wait_for bounds the whole call; httpx only bounds the gap between bytes
                resp = await asyncio.wait_for(client.post(f"{OLLAMA_URL}/api/generate", json=payload), timeout_s)
                resp.raise_for_status()
            except TimeoutError as exc:
                raise NodeError(f"L'IA n'a pas répondu en {timeout_s:.0f} s (modèle trop lourd pour cette machine ?)") from exc
            except httpx.HTTPError as exc:
                raise NodeError(f"IA locale injoignable ({OLLAMA_URL}) : {exc}") from exc
            text = _THINK.sub("", resp.json().get("response", "")).strip()
            value: Any = text
            if want_json:
                try:
                    value = json.loads(text)
                except ValueError as exc:
                    raise NodeError(f"Réponse de l'IA non JSON : {text[:200]}") from exc
            out.append({**item, field: value})
    return {"main": out}


# --------------------------------------------------------------------- end

async def flow_end(node: dict, items: list, ctx: Any) -> dict:
    """Closing point: remembers which end the items reached; the runner derives the
    run's final status (and message) from the ends reached."""
    ends = getattr(ctx, "ends", None)
    if ends is not None and items:
        cfg = node.get("config") or {}
        ends.append({
            "node_id": node["id"], "name": node.get("name") or "Fin",
            "result": cfg.get("result", "success"), "count": len(items),
            "message": render(cfg.get("message", ""), items[0], {"nombre": len(items)}),
        })
    return {}


EXECUTORS = {
    "flow.end": flow_end,
    "trigger.manual": passthrough,
    "trigger.schedule": passthrough,
    "trigger.webhook": passthrough,
    "robot.run": robot_run,
    "logic.if": logic_if,
    "logic.switch": logic_switch,
    "logic.wait": logic_wait,
    "data.read_file": data_read_file,
    "data.filter": data_filter,
    "data.set": data_set,
    "data.write_file": data_write_file,
    "http.request": http_request,
    "email.send": email_send,
    "ai.prompt": ai_prompt,
}
