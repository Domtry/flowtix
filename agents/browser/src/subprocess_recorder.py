"""Subprocess-based recorder — launches any application and captures user actions.

Uses Windows low-level hooks (mouse + keyboard) and UI Automation to identify
elements under the cursor. Works with any Windows application: legacy browsers,
Java apps, native Win32/WPF/UWP.
"""

import asyncio
import ctypes
import ctypes.wintypes
import logging
import queue
import threading
import time
from typing import Any

from .recorder import EventType, RecordedEvent
from .vision import SnapshotGrabber, capture_click_snapshot, encode_snapshot

logger = logging.getLogger(__name__)

try:
    from pywinauto import Desktop
    from pywinauto.uia_element_info import UIAElementInfo
    HAS_PYWINAUTO = True
except ImportError:
    HAS_PYWINAUTO = False

# --- Win32 constants ---
WH_MOUSE_LL = 14
WH_KEYBOARD_LL = 13
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.wintypes.LPARAM,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, HOOKPROC, ctypes.wintypes.HINSTANCE, ctypes.wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = ctypes.c_void_p

user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
user32.CallNextHookEx.restype = ctypes.wintypes.LPARAM

user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL

user32.GetMessageW.argtypes = [
    ctypes.POINTER(ctypes.wintypes.MSG), ctypes.wintypes.HWND,
    ctypes.c_uint, ctypes.c_uint,
]
user32.GetMessageW.restype = ctypes.wintypes.BOOL

user32.PostThreadMessageW.argtypes = [
    ctypes.wintypes.DWORD, ctypes.c_uint, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
user32.PostThreadMessageW.restype = ctypes.wintypes.BOOL

user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = ctypes.wintypes.HWND

user32.GetWindowTextW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.RECT)]
user32.GetWindowRect.restype = ctypes.wintypes.BOOL

user32.WindowFromPoint.argtypes = [ctypes.wintypes.POINT]
user32.WindowFromPoint.restype = ctypes.wintypes.HWND
user32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint]
user32.GetAncestor.restype = ctypes.wintypes.HWND
GA_ROOT = 2

kernel32.GetModuleHandleW.argtypes = [ctypes.wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = ctypes.wintypes.HMODULE

user32.GetKeyboardState.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
user32.GetKeyboardState.restype = ctypes.wintypes.BOOL

user32.ToUnicodeEx.argtypes = [
    ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_ubyte),
    ctypes.wintypes.LPWSTR, ctypes.c_int, ctypes.c_uint, ctypes.wintypes.HKL,
]
user32.ToUnicodeEx.restype = ctypes.c_int

user32.GetKeyboardLayout.argtypes = [ctypes.wintypes.DWORD]
user32.GetKeyboardLayout.restype = ctypes.wintypes.HKL


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.wintypes.POINT),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


SPECIAL_KEYS: dict[int, str] = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x1B: "Escape",
    0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x2E: "Delete", 0x2D: "Insert", 0x24: "Home", 0x23: "End",
    0x21: "PageUp", 0x22: "PageDown",
}

MODIFIER_VKS = {0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}

VK_NAMES: dict[int, str] = {
    **SPECIAL_KEYS,
    0x20: "Space", 0x10: "Shift", 0x11: "Ctrl", 0x12: "Alt",
}


user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetKeyState.argtypes = [ctypes.c_int]
user32.GetKeyState.restype = ctypes.c_short
user32.GetWindowThreadProcessId.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD

VK_PACKET = 0xE7
TOUNICODE_NO_STATE_CHANGE = 0x4  # don't disturb the user's pending dead key
DEAD_TO_COMBINING = {"^": "̂", "¨": "̈", "`": "̀", "´": "́", "~": "̃"}


def _foreground_layout() -> int:
    hwnd = user32.GetForegroundWindow()
    tid = user32.GetWindowThreadProcessId(hwnd, None) if hwnd else 0
    return user32.GetKeyboardLayout(tid)


def _translate_key(vk: int, scan: int) -> tuple[str, bool, dict]:
    """Translate a key at the exact moment it is pressed.

    Must run inside the hook: modifier state (Shift, AltGr, Caps Lock) and the
    target window's layout are only correct at that instant. Returns
    (text, is_dead_key, modifiers).
    """
    def down(k: int) -> bool:
        return bool(user32.GetAsyncKeyState(k) & 0x8000)

    mods = {"ctrl": down(0x11), "alt": down(0x12), "shift": down(0x10)}

    if vk == VK_PACKET:
        return chr(scan), False, mods

    state = (ctypes.c_ubyte * 256)()
    for k in (0x10, 0xA0, 0xA1, 0x11, 0xA2, 0xA3, 0x12, 0xA4, 0xA5):
        if down(k):
            state[k] = 0x80
    if user32.GetKeyState(0x14) & 1:
        state[0x14] = 0x01
    if user32.GetKeyState(0x90) & 1:
        state[0x90] = 0x01

    buf = ctypes.create_unicode_buffer(8)
    n = user32.ToUnicodeEx(vk, scan, state, buf, 8, TOUNICODE_NO_STATE_CHANGE, _foreground_layout())
    if n < 0:
        return buf.value[:1], True, mods
    text = buf.value[:n] if n > 0 else ""
    return (text if text.isprintable() else ""), False, mods


def _compose_dead(dead: str, text: str) -> str:
    """'^' + 'e' -> 'ê'; falls back to both characters when they don't combine."""
    import unicodedata
    mark = DEAD_TO_COMBINING.get(dead)
    if mark and text:
        composed = unicodedata.normalize("NFC", text[0] + mark)
        if len(composed) == 1:
            return composed + text[1:]
    return dead + text


def _vk_to_name(vk: int) -> str:
    if vk in VK_NAMES:
        return VK_NAMES[vk]
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x70 <= vk <= 0x7B:
        return f"F{vk - 0x6F}"
    return f"VK_{vk:#04x}"


def _element_at_point(x: int, y: int) -> dict[str, Any]:
    """Build a rich fingerprint of the element at screen coordinates."""
    result: dict[str, Any] = {"x": x, "y": y}
    if not HAS_PYWINAUTO:
        return result
    try:
        desktop = Desktop(backend="uia")
        elem = desktop.from_point(x, y)
        info = elem.element_info
        result["name"] = info.name or ""
        result["control_type"] = info.control_type or ""
        result["class_name"] = info.class_name or ""
        result["automation_id"] = getattr(info, "automation_id", "") or ""
        if info.rectangle:
            result["rect"] = {
                "left": info.rectangle.left,
                "top": info.rectangle.top,
                "right": info.rectangle.right,
                "bottom": info.rectangle.bottom,
            }

        # UIA parent path (up to 4 levels)
        uia_path = []
        try:
            current = elem
            for _ in range(4):
                parent = current.parent()
                if parent is None:
                    break
                pi = parent.element_info
                uia_path.append(f"{pi.control_type or '?'}/{pi.name or ''}")
                current = parent
            result["uia_path"] = uia_path
        except Exception:
            pass

        # Window-relative position (percentage)
        try:
            top_win = elem.top_level_parent()
            if top_win:
                win_rect = top_win.rectangle()
                win_w = win_rect.width()
                win_h = win_rect.height()
                if win_w > 0 and win_h > 0:
                    result["window_title"] = top_win.window_text() or ""
                    result["relative_x"] = round((x - win_rect.left) / win_w, 4)
                    result["relative_y"] = round((y - win_rect.top) / win_h, 4)
                    result["window_rect"] = {
                        "left": win_rect.left, "top": win_rect.top,
                        "right": win_rect.right, "bottom": win_rect.bottom,
                    }
        except Exception:
            pass

        # Nearby anchor elements (labels/static text within 200px)
        try:
            parent_win = elem.top_level_parent()
            if parent_win and info.rectangle:
                anchors = []
                cx = (info.rectangle.left + info.rectangle.right) // 2
                cy = (info.rectangle.top + info.rectangle.bottom) // 2
                for child in parent_win.descendants(control_type="Text"):
                    try:
                        ci = child.element_info
                        if not ci.name or not ci.rectangle:
                            continue
                        acx = (ci.rectangle.left + ci.rectangle.right) // 2
                        acy = (ci.rectangle.top + ci.rectangle.bottom) // 2
                        dx, dy = acx - cx, acy - cy
                        if abs(dx) < 200 and abs(dy) < 200 and (dx != 0 or dy != 0):
                            anchors.append({
                                "name": ci.name,
                                "control_type": ci.control_type or "",
                                "dx": dx, "dy": dy,
                            })
                            if len(anchors) >= 3:
                                break
                    except Exception:
                        continue
                if anchors:
                    result["anchors"] = anchors
        except Exception:
            pass

    except Exception:
        pass
    return result


EXCLUDED_TITLES = {"flowtix", "claude", "visual studio code", "code - oss", "windows powershell", "command prompt"}


def _is_excluded_title(title: str) -> bool:
    t = title.lower()
    return any(x in t for x in EXCLUDED_TITLES)


class _InputHookThread(threading.Thread):
    """Background thread that installs low-level mouse/keyboard hooks.

    Captures events from all windows except IDE/terminal windows.
    """

    def __init__(self, event_queue: queue.Queue, target_window_title: str = "") -> None:
        super().__init__(daemon=True)
        self._queue = event_queue
        self._thread_id: int | None = None
        self._mouse_hook = None
        self._kb_hook = None
        self._mouse_proc: HOOKPROC | None = None
        self._kb_proc: HOOKPROC | None = None
        self.target_title = target_window_title.lower()
        self._fg_log_count = 0
        # Pointer trajectory since the last click; only touched from the hook thread.
        self._path: list[tuple[int, int, float]] = []

    def _is_target_foreground(self) -> bool:
        """Check if the foreground window is a target (not an excluded tool window)."""
        try:
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return True
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value.lower()
            for excl in EXCLUDED_TITLES:
                if excl in title:
                    return False
            return True
        except Exception:
            return True

    def run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()

        _first_click = [True]

        def _get_fg_window_info() -> tuple[str, tuple[int, int, int, int]]:
            """Get foreground window title and rect (left, top, w, h) via pure Win32."""
            try:
                hwnd = user32.GetForegroundWindow()
                if not hwnd:
                    return ("", (0, 0, 0, 0))
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buf, 512)
                rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                return (buf.value, (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top))
            except Exception:
                return ("", (0, 0, 0, 0))

        def _window_info_at(pt) -> tuple[str, tuple[int, int, int, int]]:
            """Top-level window under the pointer. At mouse-down the foreground window is
            still the previous one (a click on the Studio is recorded "in" ORASS, the click
            that activates ORASS "in" the Studio), so the click's window is the one under it."""
            try:
                hwnd = user32.GetAncestor(user32.WindowFromPoint(pt), GA_ROOT)
                if not hwnd:
                    return _get_fg_window_info()
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buf, 512)
                rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                return (buf.value, (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top))
            except Exception:
                return _get_fg_window_info()

        grabber = SnapshotGrabber()

        def mouse_callback(nCode: int, wParam: int, lParam: int) -> int:
            try:
                if nCode >= 0 and wParam == WM_MOUSEMOVE:
                    ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    now = time.time()
                    path = self._path
                    if not path or abs(ms.pt.x - path[-1][0]) + abs(ms.pt.y - path[-1][1]) >= PATH_MIN_STEP:
                        path.append((ms.pt.x, ms.pt.y, now))
                        if len(path) > PATH_MAX_POINTS:
                            del path[: len(path) - PATH_MAX_POINTS]
                elif nCode >= 0 and wParam in (WM_LBUTTONDOWN, WM_RBUTTONDOWN):
                    ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    win_title, win_rect = _window_info_at(ms.pt)
                    if not _is_excluded_title(win_title):
                        kind = "click" if wParam == WM_LBUTTONDOWN else "right_click"
                        # Grab now: a menu closes a few ms after the click.
                        el, ctx = grabber.grab(ms.pt.x, ms.pt.y)
                        path, self._path = self._path, []
                        self._queue.put_nowait((kind, ms.pt.x, ms.pt.y, time.time(), win_title, win_rect, el, ctx, path))
                        if _first_click[0]:
                            print(f"[hooks] first click captured: {kind} at ({ms.pt.x},{ms.pt.y}) win='{win_title[:40]}'", flush=True)
                            _first_click[0] = False
            except Exception:
                pass
            return user32.CallNextHookEx(self._mouse_hook, nCode, wParam, lParam)

        def kb_callback(nCode: int, wParam: int, lParam: int) -> int:
            try:
                if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    if kb.vkCode == VK_ESCAPE:
                        # Escape ends the recording; swallowed so the application
                        # doesn't react to it (close a dialog…) and it isn't recorded
                        self._queue.put_nowait(("escape", 0, 0, time.time()))
                        return 1
                    if self._is_target_foreground():
                        text, dead, mods = ("", False, {})
                        if kb.vkCode not in MODIFIER_VKS:
                            text, dead, mods = _translate_key(kb.vkCode, kb.scanCode)
                        win_title, _ = _get_fg_window_info()
                        self._queue.put_nowait(("keydown", kb.vkCode, 0, time.time(), text, dead, mods, win_title))
            except Exception as e:
                print(f"[hooks] kb_callback error: {e}", flush=True)
            return user32.CallNextHookEx(self._kb_hook, nCode, wParam, lParam)

        self._mouse_proc = HOOKPROC(mouse_callback)
        self._kb_proc = HOOKPROC(kb_callback)

        hmod = kernel32.GetModuleHandleW(None)

        self._mouse_hook = user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._mouse_proc, hmod, 0,
        )
        self._kb_hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._kb_proc, hmod, 0,
        )

        print(f"[hooks] installed mouse={self._mouse_hook} kb={self._kb_hook} target='{self.target_title}'", flush=True)
        if not self._mouse_hook or not self._kb_hook:
            err = ctypes.get_last_error()
            print(f"[hooks] WARNING: hook installation failed, last_error={err}", flush=True)

        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
        if self._kb_hook:
            user32.UnhookWindowsHookEx(self._kb_hook)
        logger.info("Input hooks removed")

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)


KEYSTROKE_GROUP_TIMEOUT = 2.0
VK_ESCAPE = 0x1B


def _beep(*tones: tuple[int, int]) -> None:
    """Audible cue: the user is in the target application, not looking at the Studio."""
    def play() -> None:
        try:
            import winsound
            for freq, ms in tones:
                winsound.Beep(freq, ms)
                time.sleep(0.05)
        except Exception:
            pass
    threading.Thread(target=play, daemon=True).start()


PATH_MIN_STEP = 3          # px between kept trajectory points
PATH_MAX_POINTS = 2000
PATH_MAX_AGE = 20.0        # s: older movement is not part of reaching the next click


class SubprocessRecorder:
    def __init__(self, executable_path: str = "", window_title_pattern: str = "") -> None:
        self._executable_path = executable_path
        self._window_title_pattern = window_title_pattern
        self._events: list[RecordedEvent] = []
        self._running = False
        self._lock = asyncio.Lock()
        self._poll_task: asyncio.Task | None = None
        self._window_title: str = ""
        self._hook_thread: _InputHookThread | None = None
        self._event_queue: queue.Queue = queue.Queue()
        self._text_buffer: str = ""
        self._text_buffer_ts: float = 0.0
        self._pending_dead: str = ""
        self._text_buffer_window: str = ""
        self._prev_click: tuple[int, int, float] | None = None
        self._last_click_target: dict = {}
        # countdown before capture starts, and Escape to end the recording
        self.armed = False
        self.stop_requested = False

    def state(self) -> dict:
        return {
            "armed": self.armed,
            "remaining_s": 0.0,
            "stop_requested": self.stop_requested,
            "event_count": len(self._events),
        }

    async def start(self, url: str, keep_session: bool = False) -> None:
        """keep_session: record in the application already open (no launch, no
        opening step), so the process continues an existing session when replayed.
        (The countdown before a recording is handled by the agent, before start().)"""
        loop = asyncio.get_event_loop()
        if keep_session:
            self._running = True
            self._arm()
            print("[recorder] continuing the open session: application not launched", flush=True)
            return

        def _launch() -> int:
            SW_SHOWNORMAL = 1
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "open", self._executable_path, url or None, None, SW_SHOWNORMAL,
            )
            if result <= 32:
                raise OSError(f"ShellExecute failed (code {result}) for {self._executable_path}")
            return result

        await loop.run_in_executor(None, _launch)

        self._running = True
        self._events.append(RecordedEvent(
            timestamp=time.time(),
            event_type=EventType.NAVIGATE,
            url=url,
            metadata={"executable": self._executable_path},
        ))

        await asyncio.sleep(2)

        if HAS_PYWINAUTO:
            try:
                title = await loop.run_in_executor(None, self._find_window_title)
                if title:
                    self._window_title = title
                    self._events.append(RecordedEvent(
                        timestamp=time.time(),
                        event_type=EventType.PAGE_LOAD,
                        url=url,
                        metadata={"window_title": title},
                    ))
            except Exception:
                pass

        self._arm()

    def _arm(self) -> None:
        self._start_hooks()
        self.armed = True
        _beep((880, 120), (880, 120))  # recording starts now
        print("[recorder] capture started (Escape stops the recording)", flush=True)

    def _start_hooks(self) -> None:
        if self._window_title_pattern:
            target_filter = self._window_title_pattern.lower()
        else:
            exe_name = self._executable_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            target_filter = exe_name.replace(".exe", "").lower()

        self._hook_thread = _InputHookThread(self._event_queue, target_filter)
        self._hook_thread.start()

        self._poll_task = asyncio.create_task(self._process_hook_events())

    def _find_window_title(self) -> str:
        if not HAS_PYWINAUTO:
            return ""
        try:
            exe_name = self._executable_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].lower()
            desktop = Desktop(backend="uia")
            for win in desktop.windows():
                try:
                    title = win.window_text()
                    if title and exe_name.replace(".exe", "") in title.lower():
                        return title
                except Exception:
                    continue
        except Exception:
            pass
        return ""

    async def _flush_text_buffer(self) -> None:
        if self._text_buffer:
            print(f"[hooks] flushing text buffer: '{self._text_buffer}'", flush=True)
            async with self._lock:
                self._events.append(RecordedEvent(
                    timestamp=self._text_buffer_ts,
                    event_type=EventType.INPUT,
                    target=self._last_click_target,
                    value=self._text_buffer,
                    metadata={"grouped": True, "window_title": self._text_buffer_window},
                ))
            self._text_buffer = ""
            self._text_buffer_window = ""
            self._text_buffer_ts = 0.0

    def _relative_path(self, path: list[tuple[int, int, float]], x: int, y: int, ts: float) -> list[list[int]]:
        """Trajectory from the previous click to this one as [dx, dy, ms] offsets from
        the previous click. Replay anchors it on where that click was visually found,
        so it doesn't depend on absolute screen positions."""
        prev = self._prev_click
        self._prev_click = (x, y, ts)
        if prev is None or ts - prev[2] > PATH_MAX_AGE:
            return []
        px, py, pt = prev
        rel = [[px_ - px, py_ - py, int((t - pt) * 1000)] for px_, py_, t in path if t >= pt]
        rel.append([x - px, y - py, int((ts - pt) * 1000)])
        return rel

    async def _process_hook_events(self) -> None:
        """Drain the hook queue and convert raw input into RecordedEvents."""
        loop = asyncio.get_event_loop()
        while self._running:
            await asyncio.sleep(0.05)
            batch: list[tuple] = []
            while not self._event_queue.empty():
                try:
                    batch.append(self._event_queue.get_nowait())
                except queue.Empty:
                    break

            now = time.time()
            if self._text_buffer and not batch and (now - self._text_buffer_ts) > KEYSTROKE_GROUP_TIMEOUT:
                await self._flush_text_buffer()

            for raw in batch:
                kind = raw[0]
                ts = raw[3]

                if self.stop_requested:
                    continue  # Escape pressed: nothing after it belongs to the process
                if kind == "escape":
                    self.stop_requested = True
                    _beep((440, 350))
                    print("[recorder] Escape pressed: stop requested", flush=True)
                    continue

                if kind in ("click", "right_click"):
                    await self._flush_text_buffer()
                    x, y = raw[1], raw[2]
                    win_title = raw[4] if len(raw) > 4 else ""
                    win_rect = raw[5] if len(raw) > 5 else (0, 0, 0, 0)
                    wl, wt, ww, wh = win_rect

                    rel_x = round((x - wl) / ww, 4) if ww > 0 else None
                    rel_y = round((y - wt) / wh, 4) if wh > 0 else None

                    el, ctx = (raw[6], raw[7]) if len(raw) > 7 else (None, None)
                    if ctx is not None:
                        snapshot = await loop.run_in_executor(None, encode_snapshot, el, ctx)
                    else:
                        snapshot = await loop.run_in_executor(None, capture_click_snapshot, x, y)
                    path = self._relative_path(raw[8] if len(raw) > 8 else [], x, y, ts)

                    target = await loop.run_in_executor(None, _element_at_point, x, y)
                    selector = ""
                    tag = target.get("control_type", "")
                    if target.get("automation_id"):
                        selector = f"#{target['automation_id']}"
                    elif target.get("name"):
                        selector = f'{tag}[name="{target["name"]}"]'

                    click_target = {
                        "selector": selector,
                        "tag": tag,
                        "text": target.get("name", ""),
                        "class_name": target.get("class_name", ""),
                        "rect": target.get("rect"),
                    }
                    self._last_click_target = click_target

                    async with self._lock:
                        self._events.append(RecordedEvent(
                            timestamp=ts,
                            event_type=EventType.CLICK,
                            target=click_target,
                            metadata={
                                "x": x, "y": y,
                                "button": "right" if kind == "right_click" else "left",
                                "automation_id": target.get("automation_id", ""),
                                "screenshot_b64": snapshot.get("element_b64", ""),
                                "context_screenshot_b64": snapshot.get("context_b64", ""),
                                "dpi_scale": snapshot.get("dpi_scale", 1.0),
                                "uia_path": target.get("uia_path", []),
                                "anchors": target.get("anchors", []),
                                "relative_x": rel_x,
                                "relative_y": rel_y,
                                "window_title": win_title,
                                "window_rect": {"left": wl, "top": wt, "right": wl + ww, "bottom": wt + wh} if ww > 0 else None,
                                "path_from_prev": path,
                            },
                        ))

                elif kind == "keydown":
                    vk = raw[1]

                    if vk in MODIFIER_VKS:
                        continue
                    text, dead, mods, key_window = raw[4], raw[5], raw[6], raw[7]

                    if dead:
                        self._pending_dead = text
                        continue

                    # Ctrl/Alt alone = shortcut; Ctrl+Alt producing a char = AltGr.
                    is_shortcut = (mods.get("ctrl") or mods.get("alt")) and not text

                    if text and not is_shortcut:
                        if self._pending_dead:
                            text = _compose_dead(self._pending_dead, text)
                            self._pending_dead = ""
                        if self._text_buffer and (
                            (ts - self._text_buffer_ts) > KEYSTROKE_GROUP_TIMEOUT
                            or key_window != self._text_buffer_window
                        ):
                            await self._flush_text_buffer()
                        if not self._text_buffer:
                            self._text_buffer_window = key_window
                        self._text_buffer += text
                        self._text_buffer_ts = ts
                    elif vk == 0x08 and self._text_buffer:
                        self._text_buffer = self._text_buffer[:-1]
                        self._text_buffer_ts = ts
                    else:
                        self._pending_dead = ""
                        await self._flush_text_buffer()
                        key_name = _vk_to_name(vk)
                        async with self._lock:
                            self._events.append(RecordedEvent(
                                timestamp=ts,
                                event_type=EventType.KEYDOWN,
                                value=key_name,
                                metadata={"vk_code": vk, "key": key_name,
                                          "window_title": key_window,
                                          "ctrl": mods.get("ctrl", False),
                                          "alt": mods.get("alt", False),
                                          "shift": mods.get("shift", False)},
                            ))

    async def collect_events(self) -> list[RecordedEvent]:
        async with self._lock:
            return list(self._events)

    async def stop(self) -> list[RecordedEvent]:
        self._running = False
        await self._flush_text_buffer()

        if self._hook_thread:
            self._hook_thread.stop()
            self._hook_thread.join(timeout=3)
            self._hook_thread = None

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        events = await self.collect_events()
        return events

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def events(self) -> list[RecordedEvent]:
        return list(self._events)

    @property
    def _page(self) -> None:
        return None
