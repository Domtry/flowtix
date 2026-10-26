"""Windows desktop replay engine — executes process steps via pywinauto."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from .locators import locate_element

logger = structlog.get_logger()


@dataclass
class WinStepResult:
    step_id: str
    success: bool
    duration_ms: int = 0
    error: str | None = None
    screenshot: bytes | None = None


@dataclass
class WinReplayResult:
    success: bool
    steps: list[WinStepResult] = field(default_factory=list)
    duration_ms: int = 0


class WindowsReplayEngine:
    """Replays process steps on Windows desktop applications."""

    def __init__(self, backend: str = "uia") -> None:
        self._backend = backend

    async def replay(
        self,
        definition: dict,
        inputs: dict[str, Any] | None = None,
        on_step: Any = None,
    ) -> WinReplayResult:
        inputs = inputs or {}
        process = definition.get("process", definition)
        steps = process.get("steps", [])

        results: list[WinStepResult] = []
        overall_start = time.monotonic()
        success = True

        for step in steps:
            step_id = step.get("id", "unknown")
            start = time.monotonic()
            try:
                await self._execute_step(step, inputs)
                duration = int((time.monotonic() - start) * 1000)
                result = WinStepResult(step_id=step_id, success=True, duration_ms=duration)
            except Exception as exc:
                duration = int((time.monotonic() - start) * 1000)
                screenshot = self._capture_screen()
                result = WinStepResult(
                    step_id=step_id, success=False, duration_ms=duration,
                    error=str(exc), screenshot=screenshot,
                )
                success = False

                on_error = step.get("on_error", {})
                action = on_error.get("action", "fail") if on_error else "fail"
                if action == "skip":
                    results.append(result)
                    if on_step:
                        await on_step(result)
                    continue
                elif action == "fail":
                    results.append(result)
                    if on_step:
                        await on_step(result)
                    break

            results.append(result)
            if on_step:
                await on_step(result)

        total_duration = int((time.monotonic() - overall_start) * 1000)
        return WinReplayResult(success=success, steps=results, duration_ms=total_duration)

    async def _execute_step(self, step: dict, inputs: dict) -> None:
        step_type = step.get("type", "")
        target = step.get("target", {}) or {}
        value = step.get("value")
        params = step.get("params", {}) or {}

        if isinstance(value, str):
            value = self._resolve_vars(value, inputs)
        for k, v in params.items():
            if isinstance(v, str):
                params[k] = self._resolve_vars(v, inputs)

        match step_type:
            case "win.click":
                located = locate_element(target, self._get_window(params))
                self._do_click(located.control, located.strategy)

            case "win.right_click":
                located = locate_element(target, self._get_window(params))
                self._do_click(located.control, located.strategy, button="right")

            case "win.dblclick":
                located = locate_element(target, self._get_window(params))
                self._do_dblclick(located.control, located.strategy)

            case "win.fill":
                located = locate_element(target, self._get_window(params))
                self._do_fill(located.control, located.strategy, value or "")

            case "win.key_press":
                key = params.get("key", "")
                self._do_key_press(key)

            case "win.select":
                located = locate_element(target, self._get_window(params))
                self._do_select(located.control, located.strategy, value or "")

            case s if s.startswith("win.window_"):
                action = s.removeprefix("win.window_")
                self._do_window_action(action, params)

            case "win.launch":
                self._do_launch(params)

            case _:
                raise ValueError(f"Unknown Windows step type: {step_type}")

    def _get_window(self, params: dict) -> Any:
        title = params.get("window_title")
        if not title:
            return None
        try:
            from pywinauto import Application
            app = Application(backend=self._backend).connect(title=title)
            return app.window(title=title)
        except Exception:
            return None

    def _do_click(self, control: Any, strategy: str, button: str = "left") -> None:
        if strategy == "coordinates":
            import pyautogui
            pyautogui.click(control["x"], control["y"], button=button)
        else:
            if button == "right":
                control.right_click_input()
            else:
                control.click_input()

    def _do_dblclick(self, control: Any, strategy: str) -> None:
        if strategy == "coordinates":
            import pyautogui
            pyautogui.doubleClick(control["x"], control["y"])
        else:
            control.double_click_input()

    def _do_fill(self, control: Any, strategy: str, text: str) -> None:
        if strategy == "coordinates":
            import pyautogui
            pyautogui.click(control["x"], control["y"])
            pyautogui.hotkey("ctrl", "a")
            pyautogui.typewrite(text, interval=0.02)
        else:
            control.set_edit_text(text)

    def _do_key_press(self, key: str) -> None:
        import pyautogui
        parts = key.lower().split("+")
        if len(parts) > 1:
            pyautogui.hotkey(*parts)
        else:
            pyautogui.press(parts[0])

    def _do_select(self, control: Any, strategy: str, value: str) -> None:
        if strategy != "coordinates":
            try:
                control.select(value)
                return
            except Exception:
                pass
        logger.warning("win.select.fallback", value=value)

    def _do_window_action(self, action: str, params: dict) -> None:
        title = params.get("title", "")
        try:
            from pywinauto import Application
            app = Application(backend=self._backend).connect(title=title)
            win = app.window(title=title)
            match action:
                case "minimize":
                    win.minimize()
                case "maximize":
                    win.maximize()
                case "restore":
                    win.restore()
                case "close":
                    win.close()
                case "focus":
                    win.set_focus()
        except Exception as exc:
            raise ValueError(f"Window action '{action}' failed: {exc}") from exc

    def _do_launch(self, params: dict) -> None:
        path = params.get("path", "")
        args = params.get("args", "")
        if not path:
            raise ValueError("win.launch requires 'path' param")
        from pywinauto import Application
        Application(backend=self._backend).start(f"{path} {args}".strip())

    def _capture_screen(self) -> bytes | None:
        try:
            import pyautogui
            from io import BytesIO
            img = pyautogui.screenshot()
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return None

    @staticmethod
    def _resolve_vars(text: str, inputs: dict) -> str:
        import re
        def replacer(m: re.Match) -> str:
            var_path = m.group(1)
            parts = var_path.split(".")
            if parts[0] == "inputs" and len(parts) > 1:
                return str(inputs.get(parts[1], m.group(0)))
            return m.group(0)
        return re.sub(r"\$\{([^}]+)\}", replacer, text)
