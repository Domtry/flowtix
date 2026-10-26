"""Windows element locator strategies — UI Automation, text, image, coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class LocatorResult:
    control: Any
    strategy: str
    confidence: float = 1.0


def locate_element(target: dict, window: Any = None) -> LocatorResult:
    """Find a Windows UI element using the hierarchical strategy from the target dict.

    Priority: automation_id > control_type+name > title > text > coordinates.
    Falls back through the chain until a match is found.
    """
    strategy = target.get("strategy", "dom")

    if strategy == "dom" and target.get("selector"):
        result = _locate_by_automation_id(target, window)
        if result:
            return result

    if strategy == "accessibility" or target.get("role"):
        result = _locate_by_role(target, window)
        if result:
            return result

    if target.get("name") or target.get("text"):
        result = _locate_by_text(target, window)
        if result:
            return result

    if target.get("coordinates"):
        coords = target["coordinates"]
        return LocatorResult(
            control={"x": coords.get("x", 0), "y": coords.get("y", 0)},
            strategy="coordinates",
            confidence=0.3,
        )

    fallback = target.get("fallback")
    if fallback:
        logger.info("win.locator.fallback")
        return locate_element(fallback, window)

    raise ValueError(f"Cannot locate Windows element: {target}")


def _locate_by_automation_id(target: dict, window: Any) -> LocatorResult | None:
    if not window:
        return None
    auto_id = target.get("selector", "").lstrip("#")
    if not auto_id:
        return None
    try:
        ctrl = window.child_window(auto_id=auto_id)
        if ctrl.exists():
            return LocatorResult(control=ctrl, strategy="automation_id")
    except Exception:
        pass
    return None


def _locate_by_role(target: dict, window: Any) -> LocatorResult | None:
    if not window:
        return None
    role = target.get("role", "")
    name = target.get("name", "")
    if not role:
        return None
    try:
        ctrl = window.child_window(control_type=role, title=name or None)
        if ctrl.exists():
            return LocatorResult(control=ctrl, strategy="accessibility", confidence=0.9)
    except Exception:
        pass
    return None


def _locate_by_text(target: dict, window: Any) -> LocatorResult | None:
    if not window:
        return None
    text = target.get("name") or target.get("text", "")
    if not text:
        return None
    try:
        ctrl = window.child_window(title=text)
        if ctrl.exists():
            return LocatorResult(control=ctrl, strategy="text", confidence=0.7)
    except Exception:
        pass
    return None
