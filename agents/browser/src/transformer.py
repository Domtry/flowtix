"""Event-to-scenario transformer.

Takes raw recorded events and produces a structured process definition
conforming to the process-schema v1.0.
"""

from uuid import uuid4

from .recorder import EventType, RecordedEvent


def transform_events(events: list[RecordedEvent], process_name: str = "Recorded Process") -> dict:
    steps = []
    previous_url = ""
    input_buffer: dict | None = None

    for event in events:
        # Flush pending input buffer if a different event arrives
        if input_buffer and (
            event.event_type != EventType.INPUT
            or _target_key(event.target) != input_buffer["target_key"]
        ):
            steps.append(_make_fill_step(input_buffer))
            input_buffer = None

        match event.event_type:
            case EventType.NAVIGATE:
                if event.url != previous_url:
                    steps.append({
                        "id": _step_id(),
                        "type": "browser.navigate",
                        "label": f"Navigate to {_short_url(event.url)}",
                        "params": {"url": event.url},
                        "timeout_ms": 30000,
                    })
                    previous_url = event.url

            case EventType.PAGE_LOAD:
                if event.url != previous_url:
                    steps.append({
                        "id": _step_id(),
                        "type": "browser.wait",
                        "label": f"Wait for page {_short_url(event.url)}",
                        "params": {"event": "load", "url": event.url},
                        "timeout_ms": 30000,
                    })
                    previous_url = event.url

            case EventType.CLICK | EventType.DBLCLICK:
                target = _build_target(event.target)
                step_type = "ui.click" if event.event_type == EventType.CLICK else "ui.dblclick"
                label_text = event.target.get("text", "")[:50] or event.target.get("selector", "")
                step_data: dict = {
                    "id": _step_id(),
                    "type": step_type,
                    "label": f"Click '{label_text}'",
                    "target": target,
                }
                if event.metadata:
                    step_data["metadata"] = event.metadata
                steps.append(step_data)

            case EventType.INPUT:
                meta = event.metadata or {}
                if meta.get("grouped"):
                    if input_buffer:
                        steps.append(_make_fill_step(input_buffer))
                        input_buffer = None
                    target = _build_target(event.target) if event.target else {"strategy": "dom"}
                    name = event.target.get("text", "") or event.target.get("name", "") or event.target.get("selector", "") if event.target else ""
                    steps.append({
                        "id": _step_id(),
                        "type": "ui.fill",
                        "label": f"Type '{(event.value or '')[:30]}'",
                        "target": target,
                        "value": event.value or "",
                        "metadata": event.metadata,
                    })
                else:
                    key = _target_key(event.target)
                    if input_buffer and input_buffer["target_key"] == key:
                        input_buffer["value"] = event.value or ""
                        input_buffer["timestamp"] = event.timestamp
                    else:
                        if input_buffer:
                            steps.append(_make_fill_step(input_buffer))
                        input_buffer = {
                            "target_key": key,
                            "target": event.target,
                            "value": event.value or "",
                            "timestamp": event.timestamp,
                        }

            case EventType.CHANGE:
                target = _build_target(event.target)
                tag = event.target.get("tag", "")
                if tag == "select":
                    steps.append({
                        "id": _step_id(),
                        "type": "ui.select",
                        "label": f"Select '{event.value}'",
                        "target": target,
                        "value": event.value,
                    })

            case EventType.KEYDOWN:
                meta = event.metadata or {}
                key = meta.get("key", "")
                modifiers = []
                if meta.get("ctrl"):
                    modifiers.append("Control")
                if meta.get("alt"):
                    modifiers.append("Alt")
                if meta.get("shift"):
                    modifiers.append("Shift")
                combo = "+".join(modifiers + [key]) if modifiers else key
                steps.append({
                    "id": _step_id(),
                    "type": "keyboard.press",
                    "label": f"Press {combo}",
                    "params": {"key": combo},
                    "metadata": {"window_title": meta.get("window_title", "")},
                })

            case EventType.SCROLL:
                meta = event.metadata or {}
                steps.append({
                    "id": _step_id(),
                    "type": "ui.scroll",
                    "label": "Scroll page",
                    "params": {"x": meta.get("scrollX", 0), "y": meta.get("scrollY", 0)},
                })

            case EventType.DIALOG:
                meta = event.metadata or {}
                steps.append({
                    "id": _step_id(),
                    "type": "browser.dialog",
                    "label": f"Handle dialog: {meta.get('type', 'alert')}",
                    "params": {"action": "accept", "message": meta.get("message", "")},
                })

    # Flush remaining input buffer
    if input_buffer:
        steps.append(_make_fill_step(input_buffer))

    return {
        "schema_version": "1.0",
        "process": {
            "id": str(uuid4()),
            "name": process_name,
            "steps": steps,
        },
    }


def _step_id() -> str:
    return f"step-{uuid4().hex[:8]}"


def _short_url(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    path = p.path.rstrip("/")
    return path if path else p.netloc


def _target_key(target: dict) -> str:
    return target.get("selector", "") or target.get("name", "") or str(target.get("rect", ""))


def _build_target(target: dict) -> dict:
    result: dict = {"strategy": "dom"}
    selector = target.get("selector", "")
    if selector:
        result["selector"] = selector
    role = target.get("role", "")
    if role:
        result["role"] = role
    aria_label = target.get("ariaLabel", "")
    if aria_label:
        result["ariaLabel"] = aria_label
    name = aria_label or target.get("name", "")
    if name:
        result["name"] = name
    text = target.get("text", "")
    if text:
        result["text"] = text[:100]
    tag = target.get("tag", "")
    if tag:
        result["tag"] = tag
    placeholder = target.get("placeholder", "")
    if placeholder:
        result["placeholder"] = placeholder
    rect = target.get("rect")
    if rect:
        result["coordinates"] = rect
    return result


def _make_fill_step(buf: dict) -> dict:
    target = _build_target(buf["target"])
    name = buf["target"].get("name", "") or buf["target"].get("selector", "")
    return {
        "id": _step_id(),
        "type": "ui.fill",
        "label": f"Fill '{name}'",
        "target": target,
        "value": buf["value"],
    }
