"""Subprocess-based replay engine — replays recorded steps in native Windows apps.

Uses pywinauto UI Automation to locate elements and Win32 API (SendInput)
to perform clicks and keyboard input. Works with any Windows application.
"""

import asyncio
import ctypes
import ctypes.wintypes
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from .replay import StepResult, ReplayResult
from .smart_target import resolve_element
from .vision import dpi_scale

logger = logging.getLogger(__name__)

try:
    from pywinauto import Desktop
    HAS_PYWINAUTO = True
except ImportError:
    HAS_PYWINAUTO = False

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_MOVE = 0x0001
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002

PATH_PAUSE = 0.15        # s without movement = a deliberate stop on a menu entry
PATH_MAX_PAUSE = 0.5     # a Swing submenu opens after ~0.2s; longer human pauses were reading time
PATH_SPEEDUP = 0.3       # continuous motion replayed ~3x faster
WINDOW_SEARCH_MARGIN = 300  # px around the app window: popups may overflow it
CLICK_ATTEMPTS = 3
CLICK_EFFECT_TIMEOUT = 1.2   # s to see a reaction to a click
CLICK_EFFECT_MIN_CHANGE = 0.0005  # share of pixels; above a blinking caret
PRE_CLICK_SETTLE = 3.0       # s max waiting for the window to stop redrawing

SM_CXSCREEN = 0
SM_CYSCREEN = 1

SPECIAL_KEY_VK = {
    "Enter": 0x0D, "Tab": 0x09, "Escape": 0x1B, "Backspace": 0x08,
    "Delete": 0x2E, "Space": 0x20, "Left": 0x25, "Up": 0x26,
    "Right": 0x27, "Down": 0x28, "Home": 0x24, "End": 0x23,
    "PageUp": 0x21, "PageDown": 0x22, "Insert": 0x2D,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74,
    "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79,
    "F11": 0x7A, "F12": 0x7B,
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long), ("dy", ctypes.c_long),
        ("mouseData", ctypes.wintypes.DWORD), ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD), ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD), ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("union", _INPUT_UNION)]


user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = ctypes.c_uint
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = ctypes.wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int


def _move_to(x: int, y: int) -> None:
    """Put the pointer on (x, y) the way a hand does: Java/Swing menus arm items
    and open submenus on real WM_MOUSEMOVE, which a bare SetCursorPos may not give."""
    # SetCursorPos takes virtual-desktop coordinates, so secondary monitors with
    # negative origins work (SendInput ABSOLUTE would map to the primary only).
    user32.SetCursorPos(x, y)
    nudge = (INPUT * 2)()
    for i, dx in enumerate((1, -1)):
        nudge[i].type = INPUT_MOUSE
        nudge[i].union.mi.dx = dx
        nudge[i].union.mi.dwFlags = MOUSEEVENTF_MOVE
    user32.SendInput(2, nudge, ctypes.sizeof(INPUT))


_INPUT_VAR = re.compile(r"\$\{inputs\.([^}]+)\}")


def _resolve_inputs(text, inputs: dict):
    """Replace ${inputs.<column>} with the row value. A missing column fails the
    step: typing the literal placeholder into the application would be worse."""
    if not isinstance(text, str) or "${" not in text:
        return text

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name not in inputs:
            raise RuntimeError(f"Variable absente des données : {name}")
        return str(inputs[name])

    return _INPUT_VAR.sub(repl, text)


def _follow_path(origin: tuple[int, int], path: list, scale: float) -> None:
    """Replay the recorded pointer trajectory from the previous click, anchored on
    where that click was found and scaled by the DPI ratio. Moving through the same
    menu entries, with the same pauses, opens cascading submenus like a human does.
    The last point (the destination) is skipped: it is located visually afterwards."""
    ox, oy = origin
    prev_t = 0
    for dx, dy, t in path[:-1]:
        gap = max(0, t - prev_t) / 1000
        prev_t = t
        px, py = ox + round(dx * scale), oy + round(dy * scale)
        if gap >= PATH_PAUSE:
            time.sleep(min(gap, PATH_MAX_PAUSE))  # deliberate stop: submenu opening delay
            _move_to(px, py)
        else:
            time.sleep(gap * PATH_SPEEDUP)
            user32.SetCursorPos(px, py)


def _region_image(region: tuple[int, int, int, int] | None, x: int, y: int):
    from .vision import _grab
    if region is None:
        region = (x - 400, y - 300, x + 400, y + 500)
    left, top, right, bottom = region
    return _grab(left, top, right - left, bottom - top)


def _changed(a, b) -> bool:
    import numpy as np
    if a is None or b is None or a.shape != b.shape:
        return True
    diff = np.count_nonzero(np.any(a != b, axis=2)) / (a.shape[0] * a.shape[1])
    return diff > CLICK_EFFECT_MIN_CHANGE


def _press(button: str = "left") -> None:
    down_flag = MOUSEEVENTF_LEFTDOWN if button == "left" else MOUSEEVENTF_RIGHTDOWN
    up_flag = MOUSEEVENTF_LEFTUP if button == "left" else MOUSEEVENTF_RIGHTUP
    down = INPUT()
    down.type = INPUT_MOUSE
    down.union.mi.dwFlags = down_flag
    up = INPUT()
    up.type = INPUT_MOUSE
    up.union.mi.dwFlags = up_flag
    inputs = (INPUT * 2)(down, up)
    user32.SendInput(2, inputs, ctypes.sizeof(INPUT))


def _click_at(x: int, y: int, button: str = "left") -> None:
    _move_to(x, y)
    time.sleep(0.15)

    down_flag = MOUSEEVENTF_LEFTDOWN if button == "left" else MOUSEEVENTF_RIGHTDOWN
    up_flag = MOUSEEVENTF_LEFTUP if button == "left" else MOUSEEVENTF_RIGHTUP

    down = INPUT()
    down.type = INPUT_MOUSE
    down.union.mi.dwFlags = down_flag

    up = INPUT()
    up.type = INPUT_MOUSE
    up.union.mi.dwFlags = up_flag

    inputs = (INPUT * 2)(down, up)
    user32.SendInput(2, inputs, ctypes.sizeof(INPUT))


user32.VkKeyScanExW.argtypes = [ctypes.c_wchar, ctypes.c_void_p]
user32.VkKeyScanExW.restype = ctypes.c_short
user32.GetWindowThreadProcessId.argtypes = [ctypes.wintypes.HWND, ctypes.c_void_p]
user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD
user32.GetKeyboardLayout.argtypes = [ctypes.wintypes.DWORD]
user32.GetKeyboardLayout.restype = ctypes.c_void_p
user32.GetForegroundWindow.restype = ctypes.wintypes.HWND


user32.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
user32.IsIconic.argtypes = [ctypes.wintypes.HWND]
user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [ctypes.wintypes.HWND]
user32.GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.RECT)]
_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


def _window_text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def _find_window(title: str):
    """Best visible top-level window for a recorded title. Titles may carry dynamic
    parts (machine codes, page names), so fall back to similarity."""
    import difflib
    wanted = title.lower()
    best, best_score = None, 0.0

    def cb(hwnd, _):
        nonlocal best, best_score
        if not user32.IsWindowVisible(hwnd):
            return True
        t = _window_text(hwnd).lower()
        if not t:
            return True
        score = 1.0 if t == wanted else difflib.SequenceMatcher(None, t, wanted).ratio()
        if score > best_score:
            best, best_score = hwnd, score
        return True

    user32.EnumWindows(_WNDENUMPROC(cb), 0)
    return best if best_score >= 0.6 else None


def _window_region(metadata: dict) -> tuple[int, int, int, int] | None:
    """Search area for a step: the window it was recorded in, plus a margin."""
    title = metadata.get("window_title", "")
    hwnd = _find_window(title) if title else None
    if not hwnd:
        return None
    r = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    m = WINDOW_SEARCH_MARGIN
    return (r.left - m, r.top - m, r.right + m, r.bottom + m)


def _window_anchor(metadata: dict) -> tuple[int, int] | None:
    """Where the click was inside its window (offset from the window's top-left,
    DPI-scaled), applied to the window as it is now. Never used alone: it only
    corroborates an image match (menus and toolbars keep their offset)."""
    rect = metadata.get("window_rect")
    x, y, title = metadata.get("x"), metadata.get("y"), metadata.get("window_title", "")
    if not rect or x is None or y is None or not title:
        return None
    hwnd = _find_window(title)
    if not hwnd:
        return None
    r = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    scale = dpi_scale() / (metadata.get("dpi_scale") or 1.0)
    return (r.left + round((x - rect["left"]) * scale), r.top + round((y - rect["top"]) * scale))


def _bring_to_front(hwnd) -> None:
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    # Windows only grants focus to the process that sent the last input: a
    # harmless Alt tap makes SetForegroundWindow succeed.
    seq = (INPUT * 2)(_key_input(0x12), _key_input(0x12, flags=KEYEVENTF_KEYUP))
    user32.SendInput(2, seq, ctypes.sizeof(INPUT))
    user32.SetForegroundWindow(hwnd)


def _wait_visually_stable(hwnd, timeout: float = 8.0) -> None:
    """Wait until the window stops redrawing (app finished loading)."""
    import numpy as np
    from .vision import _grab
    deadline = time.monotonic() + timeout
    prev = None
    while time.monotonic() < deadline:
        r = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 0 or h <= 0:
            time.sleep(0.3)
            continue
        img = _grab(r.left, r.top, w, h)
        if prev is not None and img is not None and prev.shape == img.shape:
            changed = np.count_nonzero(np.any(prev != img, axis=2)) / (w * h)
            if changed < 0.002:  # tolerates a blinking caret
                return
        prev = img
        time.sleep(0.15)


def _key_input(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = vk
    inp.union.ki.wScan = scan
    inp.union.ki.dwFlags = flags
    return inp


def _type_text(text: str) -> None:
    """Type with real key strokes on the target window's layout (Java apps ignore
    synthetic Unicode input); fall back to Unicode only for unmappable chars."""
    hwnd = user32.GetForegroundWindow()
    layout = user32.GetKeyboardLayout(user32.GetWindowThreadProcessId(hwnd, None) if hwnd else 0)

    for ch in text:
        res = user32.VkKeyScanExW(ch, layout)
        seq: list[INPUT] = []
        if res != -1:
            vk, shift_state = res & 0xFF, (res >> 8) & 0xFF
            mods = [m for bit, m in ((1, 0x10), (2, 0x11), (4, 0x12)) if shift_state & bit]
            seq += [_key_input(m) for m in mods]
            seq += [_key_input(vk), _key_input(vk, flags=KEYEVENTF_KEYUP)]
            seq += [_key_input(m, flags=KEYEVENTF_KEYUP) for m in reversed(mods)]
        else:
            code = ord(ch)
            seq += [_key_input(scan=code, flags=KEYEVENTF_UNICODE),
                    _key_input(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
        arr = (INPUT * len(seq))(*seq)
        user32.SendInput(len(seq), arr, ctypes.sizeof(INPUT))
        time.sleep(0.03)


def _press_key(vk: int) -> None:
    down = INPUT()
    down.type = INPUT_KEYBOARD
    down.union.ki.wVk = vk
    down.union.ki.dwFlags = 0

    up = INPUT()
    up.type = INPUT_KEYBOARD
    up.union.ki.wVk = vk
    up.union.ki.dwFlags = KEYEVENTF_KEYUP

    inputs = (INPUT * 2)(down, up)
    user32.SendInput(2, inputs, ctypes.sizeof(INPUT))


class SubprocessReplayEngine:
    def __init__(self, executable_path: str = "", slow_mo: int = 200) -> None:
        self._executable_path = executable_path
        self._slow_mo = slow_mo
        self._last_click_pos: tuple[int, int] | None = None
        self._next_step: dict | None = None

    async def replay(
        self,
        definition: dict,
        inputs: dict[str, Any] | None = None,
        on_step: Any = None,
    ) -> ReplayResult:
        inputs = inputs or {}
        process = definition.get("process", definition)
        steps = process.get("steps", [])

        loop = asyncio.get_event_loop()
        results: list[StepResult] = []
        overall_start = time.monotonic()
        success = True

        for i, step in enumerate(steps):
            self._next_step = steps[i + 1] if i + 1 < len(steps) else None
            step_id = step.get("id", "unknown")
            start = time.monotonic()
            try:
                await self._execute_step(loop, step, inputs)
                duration = int((time.monotonic() - start) * 1000)
                result = StepResult(step_id=step_id, success=True, duration_ms=duration)
            except Exception as exc:
                duration = int((time.monotonic() - start) * 1000)
                result = StepResult(
                    step_id=step_id, success=False, duration_ms=duration, error=str(exc),
                )
                on_error = step.get("on_error", {})
                action = on_error.get("action", "fail") if on_error else "fail"
                if action != "skip":
                    success = False
                if action == "skip":
                    logger.info("Step %s skipped: %s", step_id, exc)
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

            if self._slow_mo > 0:
                await asyncio.sleep(self._slow_mo / 1000)

        total = int((time.monotonic() - overall_start) * 1000)
        return ReplayResult(success=success, steps=results, duration_ms=total)

    async def _execute_step(self, loop: asyncio.AbstractEventLoop, step: dict, inputs: dict) -> None:
        step_type = step.get("type", "")
        params = step.get("params", {}) or {}
        target = step.get("target", {}) or {}
        value = step.get("value")
        metadata = step.get("metadata", {}) or {}

        value = _resolve_inputs(value, inputs)
        params = {k: _resolve_inputs(v, inputs) for k, v in params.items()}

        if step_type == "ui.fill":
            # typed values can be passwords: never log them
            logger.info("Executing step: ui.fill — %d caractère(s)", len(value or ""))
        else:
            logger.info("Executing step: %s — %s", step_type, step.get("label", ""))

        match step_type:
            case "browser.navigate":
                url = params.get("url", "")
                if self._executable_path and url:
                    SW_SHOWNORMAL = 1
                    def _launch():
                        ctypes.windll.shell32.ShellExecuteW(
                            None, "open", self._executable_path, url, None, SW_SHOWNORMAL,
                        )
                    await loop.run_in_executor(None, _launch)
                    # no fixed wait: the next step polls until its element is on screen
                    await asyncio.sleep(0.5)

            case "browser.wait":
                await asyncio.sleep(2)

            case "ui.click" | "ui.dblclick":
                hwnd = await loop.run_in_executor(None, _find_window, metadata.get("window_title", "")) \
                    if metadata.get("window_title") else None
                if hwnd:
                    if user32.GetForegroundWindow() != hwnd:
                        # continuing a session: the app may be behind the Studio or another window
                        logger.info("[focus] bringing '%s' to front before click", _window_text(hwnd))
                        await loop.run_in_executor(None, _bring_to_front, hwnd)
                    # an app still drawing a freshly loaded screen ignores clicks
                    await loop.run_in_executor(None, _wait_visually_stable, hwnd, PRE_CLICK_SETTLE)
                path = metadata.get("path_from_prev") or []
                if path and self._last_click_pos:
                    scale = dpi_scale() / (metadata.get("dpi_scale") or 1.0)
                    logger.info("[path] following %d points from %s", len(path), self._last_click_pos)
                    await loop.run_in_executor(None, _follow_path, self._last_click_pos, path, scale)
                x, y = await self._wait_for_element(step, target, metadata)
                self._last_click_pos = (x, y)
                button = metadata.get("button", "left")
                if step_type == "ui.dblclick":
                    await loop.run_in_executor(None, _click_at, x, y, button)
                    await asyncio.sleep(0.05)
                    await loop.run_in_executor(None, _click_at, x, y, button)
                else:
                    region = await loop.run_in_executor(None, _window_region, metadata)
                    reacted = await self._verified_click(loop, x, y, button, region)
                    if not reacted:
                        # some clicks legitimately change nothing (already-focused field);
                        # the next step's own wait will catch a real failure
                        logger.warning("[click] no visible reaction after %d attempts at (%d,%d)",
                                       CLICK_ATTEMPTS, x, y)
                await asyncio.sleep(0.1)

            case "ui.hover":
                x, y = await self._wait_for_element(step, target, metadata, use_llm=False)
                await loop.run_in_executor(None, _move_to, x, y)
                await asyncio.sleep(0.7)  # let the submenu open

            case "ui.fill":
                text = value or ""
                await self._ensure_window(loop, step, metadata)
                if metadata.get("screenshot_b64") or metadata.get("context_screenshot_b64"):
                    x, y = await self._wait_for_element(step, target, metadata)
                    self._last_click_pos = (x, y)
                    await loop.run_in_executor(None, _click_at, x, y, "left")
                    await asyncio.sleep(0.15)
                await loop.run_in_executor(None, _type_text, text)

            case "keyboard.press":
                key_str = params.get("key", "")
                await self._ensure_window(loop, step, metadata)
                await self._send_key_combo(loop, key_str)

            case "ui.scroll":
                pass

            case _:
                logger.warning("Subprocess replay: unsupported step type '%s', skipping", step_type)

    async def _verified_click(
        self, loop: asyncio.AbstractEventLoop, x: int, y: int, button: str, region,
    ) -> bool:
        """Click and confirm it worked. A busy app (still loading a module) silently
        drops clicks: retry once it has settled. A click that changes nothing is still
        a success when the next step's element is already on screen (e.g. the cursor
        path had opened the submenu). Returns False if no attempt is confirmed."""
        for attempt in range(1, CLICK_ATTEMPTS + 1):
            await loop.run_in_executor(None, _move_to, x, y)
            await asyncio.sleep(0.12)  # hover highlight appears before the reference shot
            before = await loop.run_in_executor(None, _region_image, region, x, y)
            await loop.run_in_executor(None, _press, button)
            deadline = time.monotonic() + CLICK_EFFECT_TIMEOUT
            while time.monotonic() < deadline:
                await asyncio.sleep(0.1)
                after = await loop.run_in_executor(None, _region_image, region, x, y)
                if _changed(before, after):
                    return True
            if await self._next_target_visible():
                logger.info("[click] no change at (%d,%d) but next element already visible: OK", x, y)
                return True
            logger.info("[click] no visible effect at (%d,%d), attempt %d/%d", x, y, attempt, CLICK_ATTEMPTS)
            await asyncio.sleep(0.6)  # beyond the double-click delay, and let the app settle
        return False

    async def _next_target_visible(self) -> bool:
        nxt = self._next_step
        if not nxt or nxt.get("type") not in ("ui.click", "ui.dblclick", "ui.fill"):
            return False
        meta = nxt.get("metadata") or {}
        if not (meta.get("screenshot_b64") or meta.get("context_screenshot_b64")):
            return False
        region = await asyncio.get_event_loop().run_in_executor(None, _window_region, meta)
        found = await resolve_element(nxt.get("target") or {}, meta, use_slow=False, region=region)
        return found is not None

    async def _ensure_window(self, loop: asyncio.AbstractEventLoop, step: dict, metadata: dict) -> None:
        """Keystrokes must land in the window they were recorded in: wait for it to
        exist (an app may still be launching), focus it, and let it finish drawing."""
        title = metadata.get("window_title", "")
        if not title:
            return
        timeout_s = max((step.get("timeout_ms") or 0) / 1000, 30.0)
        deadline = time.monotonic() + timeout_s
        hwnd = None
        while hwnd is None:
            hwnd = await loop.run_in_executor(None, _find_window, title)
            if hwnd is None:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Fenêtre introuvable après {timeout_s:.0f}s : {title}")
                await asyncio.sleep(0.5)

        if user32.GetForegroundWindow() != hwnd:
            logger.info("[focus] bringing '%s' to front", _window_text(hwnd))
            await loop.run_in_executor(None, _bring_to_front, hwnd)
        await loop.run_in_executor(None, _wait_visually_stable, hwnd)
        if user32.GetForegroundWindow() != hwnd:
            raise RuntimeError(f"Impossible de donner le focus à la fenêtre : {_window_text(hwnd)}")
        await asyncio.sleep(0.05)

    async def _wait_for_element(
        self, step: dict, target: dict, metadata: dict, use_llm: bool = True,
    ) -> tuple[int, int]:
        """Poll until the element is visually found; fail the step rather than misclick."""
        timeout_s = (step.get("timeout_ms") or 15000) / 1000
        deadline = time.monotonic() + timeout_s
        attempt = 0
        while True:
            attempt += 1
            # The LLM is slow: only consult it once the fast sources have had time.
            use_slow = use_llm and attempt >= 3
            region = await asyncio.get_event_loop().run_in_executor(None, _window_region, metadata)
            anchor = await asyncio.get_event_loop().run_in_executor(None, _window_anchor, metadata)
            found = await resolve_element(target, metadata, use_slow=use_slow, region=region, anchor=anchor)
            if found:
                return found.coords
            if time.monotonic() >= deadline:
                label = step.get("label") or target.get("text") or "?"
                raise RuntimeError(f"Element introuvable à l'écran après {timeout_s:.0f}s : {label}")
            await asyncio.sleep(0.7)

    async def _send_key_combo(self, loop: asyncio.AbstractEventLoop, key_str: str) -> None:
        parts = key_str.split("+")
        modifiers = []
        key = parts[-1] if parts else ""
        for p in parts[:-1]:
            p_lower = p.strip().lower()
            if p_lower in ("control", "ctrl"):
                modifiers.append(0x11)
            elif p_lower == "alt":
                modifiers.append(0x12)
            elif p_lower == "shift":
                modifiers.append(0x10)

        def _do():
            for m in modifiers:
                inp = INPUT()
                inp.type = INPUT_KEYBOARD
                inp.union.ki.wVk = m
                inp.union.ki.dwFlags = 0
                arr = (INPUT * 1)(inp)
                user32.SendInput(1, arr, ctypes.sizeof(INPUT))

            vk = SPECIAL_KEY_VK.get(key, 0)
            if vk:
                _press_key(vk)
            elif len(key) == 1:
                vk = ctypes.windll.user32.VkKeyScanW(ord(key)) & 0xFF
                if vk:
                    _press_key(vk)

            for m in reversed(modifiers):
                inp = INPUT()
                inp.type = INPUT_KEYBOARD
                inp.union.ki.wVk = m
                inp.union.ki.dwFlags = KEYEVENTF_KEYUP
                arr = (INPUT * 1)(inp)
                user32.SendInput(1, arr, ctypes.sizeof(INPUT))

        await loop.run_in_executor(None, _do)
