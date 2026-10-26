"""Transform WindowsEvents into process schema v1.0 steps."""

from __future__ import annotations

from typing import Any

from .recorder import WindowsEvent


def transform_windows_events(events: list[WindowsEvent]) -> dict:
    """Convert a list of WindowsEvent to a process schema v1.0 document."""
    steps: list[dict[str, Any]] = []

    for i, event in enumerate(events):
        step = _event_to_step(i, event)
        if step:
            steps.append(step)

    steps = _merge_consecutive_types(steps)

    return {
        "schema_version": "1.0",
        "process": {
            "id": "windows-recorded",
            "name": "Windows Recorded Process",
            "steps": steps,
        },
    }


def _event_to_step(index: int, event: WindowsEvent) -> dict[str, Any] | None:
    target = _build_target(event)

    match event.event_type:
        case "click":
            return {
                "id": f"step-{index}",
                "type": "win.click",
                "label": f"Click {event.name or 'element'}",
                "target": target,
            }
        case "right_click":
            return {
                "id": f"step-{index}",
                "type": "win.right_click",
                "label": f"Right-click {event.name or 'element'}",
                "target": target,
            }
        case "type":
            return {
                "id": f"step-{index}",
                "type": "win.fill",
                "label": f"Type into {event.name or 'field'}",
                "target": target,
                "value": event.value or "",
            }
        case "key_press":
            return {
                "id": f"step-{index}",
                "type": "win.key_press",
                "label": f"Press {event.key}",
                "params": {"key": event.key},
            }
        case s if s.startswith("window."):
            action = s.removeprefix("window.")
            return {
                "id": f"step-{index}",
                "type": f"win.window_{action}",
                "label": f"{action.title()} window {event.window_title or ''}".strip(),
                "params": {"title": event.window_title},
            }
        case _:
            return None


def _build_target(event: WindowsEvent) -> dict[str, Any]:
    target: dict[str, Any] = {}

    if event.automation_id:
        target["strategy"] = "dom"
        target["selector"] = f"#{event.automation_id}"
    elif event.control_type and event.name:
        target["strategy"] = "accessibility"
        target["role"] = event.control_type
        target["name"] = event.name
    elif event.name:
        target["strategy"] = "accessibility"
        target["text"] = event.name

    if event.coordinates:
        if not target:
            target["strategy"] = "coordinates"
        target["coordinates"] = event.coordinates

    if not target:
        target["strategy"] = "coordinates"
        target["coordinates"] = {"x": 0, "y": 0}

    return target


def _merge_consecutive_types(steps: list[dict]) -> list[dict]:
    """Merge consecutive win.fill steps targeting the same element."""
    if not steps:
        return steps

    merged: list[dict] = [steps[0]]
    for step in steps[1:]:
        prev = merged[-1]
        if (
            step.get("type") == "win.fill"
            and prev.get("type") == "win.fill"
            and step.get("target") == prev.get("target")
        ):
            prev["value"] = step.get("value", "")
        else:
            merged.append(step)
    return merged
