"""Windows desktop recorder — captures UI events via hooks and UI Automation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class WindowsEvent:
    timestamp: float
    event_type: str
    control_type: str | None = None
    automation_id: str | None = None
    name: str | None = None
    class_name: str | None = None
    value: str | None = None
    coordinates: dict[str, int] | None = None
    process_name: str | None = None
    window_title: str | None = None
    key: str | None = None


class WindowsRecorder:
    """Records Windows desktop interactions.

    Uses pywinauto to inspect UI state and pyautogui hooks for input capture.
    Produces WindowsEvent instances for transformation into process schema steps.
    """

    def __init__(self) -> None:
        self._recording = False
        self._events: list[WindowsEvent] = []
        self._start_time: float = 0

    @property
    def events(self) -> list[WindowsEvent]:
        return list(self._events)

    def start(self, target_process: str | None = None) -> None:
        self._recording = True
        self._events = []
        self._start_time = time.monotonic()
        self._target_process = target_process
        logger.info("win.recorder.start", target=target_process)

    def stop(self) -> list[WindowsEvent]:
        self._recording = False
        logger.info("win.recorder.stop", events=len(self._events))
        return list(self._events)

    def push_event(self, event: WindowsEvent) -> None:
        if not self._recording:
            return
        self._events.append(event)

    def capture_click(self, x: int, y: int, button: str = "left") -> None:
        if not self._recording:
            return
        control_info = self._inspect_at(x, y)
        self.push_event(WindowsEvent(
            timestamp=time.monotonic() - self._start_time,
            event_type="click" if button == "left" else "right_click",
            coordinates={"x": x, "y": y},
            **control_info,
        ))

    def capture_type(self, text: str, control_info: dict | None = None) -> None:
        if not self._recording:
            return
        info = control_info or {}
        self.push_event(WindowsEvent(
            timestamp=time.monotonic() - self._start_time,
            event_type="type",
            value=text,
            **info,
        ))

    def capture_key(self, key: str) -> None:
        if not self._recording:
            return
        self.push_event(WindowsEvent(
            timestamp=time.monotonic() - self._start_time,
            event_type="key_press",
            key=key,
        ))

    def capture_window_action(self, action: str, title: str) -> None:
        if not self._recording:
            return
        self.push_event(WindowsEvent(
            timestamp=time.monotonic() - self._start_time,
            event_type=f"window.{action}",
            window_title=title,
        ))

    def _inspect_at(self, x: int, y: int) -> dict[str, Any]:
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            element = desktop.from_point(x, y)
            wrapper = element.wrapper_object()
            return {
                "control_type": wrapper.element_info.control_type,
                "automation_id": wrapper.element_info.automation_id or None,
                "name": wrapper.element_info.name or None,
                "class_name": wrapper.element_info.class_name or None,
                "process_name": getattr(wrapper, "process_id", None),
            }
        except Exception:
            return {}
