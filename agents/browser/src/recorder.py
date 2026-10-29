"""Browser recorder — captures user actions via Playwright CDP instrumentation.

Uses page.expose_function for immediate event delivery (no polling loss),
resolves click targets to their interactive ancestor, and generates robust
CSS selectors with nth-of-type for uniqueness.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright


class EventType(str, Enum):
    CLICK = "click"
    DBLCLICK = "dblclick"
    CONTEXTMENU = "contextmenu"
    INPUT = "input"
    CHANGE = "change"
    KEYDOWN = "keydown"
    SCROLL = "scroll"
    NAVIGATE = "navigate"
    PAGE_LOAD = "page_load"
    SELECT = "select"
    FOCUS = "focus"
    FILE_CHOOSE = "file_choose"
    DIALOG = "dialog"


@dataclass
class RecordedEvent:
    timestamp: float
    event_type: str
    url: str = ""
    target: dict = field(default_factory=dict)
    value: str | None = None
    metadata: dict = field(default_factory=dict)


CAPTURE_SCRIPT = """
(() => {
    if (window.__flowtix_recording) return;
    window.__flowtix_recording = true;
    window.__flowtix_events = [];

    const emit = typeof window.__flowtix_push === 'function'
        ? (data) => { try { window.__flowtix_push(JSON.stringify(data)); } catch(_) { window.__flowtix_events.push(data); } }
        : (data) => { window.__flowtix_events.push(data); };

    const INTERACTIVE = new Set(['A','BUTTON','INPUT','SELECT','TEXTAREA','LABEL','SUMMARY','DETAILS']);
    const CLICKABLE_ROLES = new Set(['button','link','tab','menuitem','option','checkbox','radio','switch','treeitem']);

    function getInteractiveAncestor(el) {
        let cur = el;
        let depth = 0;
        while (cur && cur !== document.body && depth < 8) {
            if (INTERACTIVE.has(cur.tagName)) return cur;
            const role = cur.getAttribute && cur.getAttribute('role');
            if (role && CLICKABLE_ROLES.has(role)) return cur;
            if (cur.hasAttribute && (cur.hasAttribute('onclick') || cur.hasAttribute('tabindex'))) return cur;
            cur = cur.parentElement;
            depth++;
        }
        return el;
    }

    function getUniqueSelector(el) {
        if (!el || !el.tagName || el === document.body || el === document.documentElement) return 'body';

        // Priority 1: id
        if (el.id && document.querySelectorAll('#' + CSS.escape(el.id)).length === 1)
            return '#' + CSS.escape(el.id);

        // Priority 2: data-testid
        const testId = el.getAttribute && el.getAttribute('data-testid');
        if (testId) return '[data-testid="' + testId + '"]';

        // Priority 3: name attr (form elements)
        if (el.name && /^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(el.tagName)) {
            const sel = el.tagName.toLowerCase() + '[name="' + el.name + '"]';
            if (document.querySelectorAll(sel).length === 1) return sel;
        }

        // Priority 4: aria-label
        const ariaLabel = el.getAttribute && el.getAttribute('aria-label');
        if (ariaLabel) {
            const sel = '[aria-label="' + ariaLabel + '"]';
            if (document.querySelectorAll(sel).length === 1) return sel;
        }

        // Priority 5: role + accessible name (for Playwright get_by_role)
        const role = el.getAttribute && el.getAttribute('role');
        if (role) {
            const sel = '[role="' + role + '"]';
            if (document.querySelectorAll(sel).length === 1) return sel;
        }

        // Priority 6: build a CSS path with nth-of-type for uniqueness
        const segments = [];
        let cur = el;
        for (let i = 0; i < 5 && cur && cur !== document.body; i++) {
            let seg = cur.tagName.toLowerCase();

            if (cur.id && document.querySelectorAll('#' + CSS.escape(cur.id)).length === 1) {
                segments.unshift('#' + CSS.escape(cur.id));
                break;
            }

            if (cur.className && typeof cur.className === 'string') {
                const classes = cur.className.trim().split(/\\s+/)
                    .filter(c => c && !/^(ng-|_|css-|sc-|cdk-|mat-)/.test(c))
                    .slice(0, 2);
                if (classes.length) seg += '.' + classes.map(CSS.escape).join('.');
            }

            const parent = cur.parentElement;
            if (parent) {
                const sibs = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
                if (sibs.length > 1) seg += ':nth-of-type(' + (sibs.indexOf(cur) + 1) + ')';
            }
            segments.unshift(seg);
            cur = cur.parentElement;
        }

        const built = segments.join(' > ');
        try {
            if (document.querySelectorAll(built).length === 1) return built;
        } catch(_) {}

        return built;
    }

    function getTarget(el) {
        const text = (el.innerText || el.textContent || '').trim();
        return {
            tag: el.tagName ? el.tagName.toLowerCase() : '',
            selector: getUniqueSelector(el),
            text: text.slice(0, 200),
            type: el.type || '',
            name: el.name || '',
            role: (el.getAttribute && el.getAttribute('role')) || '',
            ariaLabel: (el.getAttribute && el.getAttribute('aria-label')) || '',
            href: el.href || '',
            placeholder: (el.getAttribute && el.getAttribute('placeholder')) || '',
            rect: el.getBoundingClientRect ? (() => {
                const r = el.getBoundingClientRect();
                return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};
            })() : null,
        };
    }

    function push(eventType, el, extra) {
        emit({
            timestamp: Date.now(),
            event_type: eventType,
            url: location.href,
            target: el ? getTarget(el) : {},
            ...extra,
        });
    }

    // ----- Click: resolve to interactive ancestor -----
    document.addEventListener('click', e => push('click', getInteractiveAncestor(e.target), {}), true);
    document.addEventListener('dblclick', e => push('dblclick', getInteractiveAncestor(e.target), {}), true);
    document.addEventListener('contextmenu', e => push('contextmenu', e.target, {}), true);

    // ----- Input: debounced -----
    let inputTimer = null;
    let lastInputEl = null;
    document.addEventListener('input', e => {
        clearTimeout(inputTimer);
        lastInputEl = e.target;
        const el = e.target;
        inputTimer = setTimeout(() => push('input', el, {value: el.value ?? ''}), 300);
    }, true);

    document.addEventListener('change', e => {
        if (inputTimer) { clearTimeout(inputTimer); inputTimer = null; }
        push('change', e.target, {value: e.target.value ?? ''});
    }, true);

    // ----- Keyboard -----
    document.addEventListener('keydown', e => {
        if (['Tab','Enter','Escape','Backspace','Delete','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key)
            || (e.ctrlKey && e.key.length === 1)
            || (e.altKey && e.key.length === 1)) {
            push('keydown', e.target, {metadata: {key: e.key, ctrl: e.ctrlKey, alt: e.altKey, shift: e.shiftKey}});
        }
    }, true);

    // ----- Scroll: debounced -----
    let scrollTimer = null;
    window.addEventListener('scroll', () => {
        clearTimeout(scrollTimer);
        scrollTimer = setTimeout(() => {
            push('scroll', document.scrollingElement, {
                metadata: {scrollX: Math.round(window.scrollX), scrollY: Math.round(window.scrollY)}
            });
        }, 500);
    }, true);

    // ----- Flush pending events before page unload -----
    window.addEventListener('beforeunload', () => {
        if (inputTimer && lastInputEl) {
            clearTimeout(inputTimer);
            inputTimer = null;
            push('input', lastInputEl, {value: lastInputEl.value ?? ''});
        }
    });
})();
"""


import os as _os

PLAYWRIGHT_FIREFOX = _os.path.expanduser(
    r"~\AppData\Local\ms-playwright\firefox-1555\firefox\firefox.exe"
)


def _detect_browser_type(path: str) -> tuple[str, str]:
    """Return (engine, effective_executable_path)."""
    lower = path.lower()
    if "firefox" in lower:
        return "firefox", PLAYWRIGHT_FIREFOX
    if "webkit" in lower or "safari" in lower:
        return "webkit", ""
    return "chromium", path


class BrowserRecorder:
    def __init__(self, executable_path: str = "") -> None:
        self._executable_path = executable_path
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._events: list[RecordedEvent] = []
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self, url: str) -> None:
        self._pw = await async_playwright().start()
        engine_name, effective_path = _detect_browser_type(self._executable_path)
        launch_opts: dict[str, Any] = {"headless": False}
        if effective_path:
            launch_opts["executable_path"] = effective_path
        engine = getattr(self._pw, engine_name)
        self._browser = await engine.launch(**launch_opts)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()

        await self._page.expose_function("__flowtix_push", self._on_push)

        self._page.on("load", self._on_page_load)
        self._page.on("dialog", self._on_dialog)
        self._page.on("filechooser", self._on_file_chooser)
        self._page.on("framenavigated", self._on_frame_navigated)
        self._context.on("page", self._on_new_page)

        await self._page.goto(url, wait_until="domcontentloaded")
        await self._inject_capture()

        self._running = True
        self._events.append(RecordedEvent(
            timestamp=time.time(),
            event_type=EventType.NAVIGATE,
            url=url,
        ))

    async def _on_push(self, data_json: str) -> None:
        data = json.loads(data_json)
        async with self._lock:
            self._events.append(RecordedEvent(
                timestamp=data.get("timestamp", time.time() * 1000) / 1000,
                event_type=data.get("event_type", "unknown"),
                url=data.get("url", ""),
                target=data.get("target", {}),
                value=data.get("value"),
                metadata=data.get("metadata", {}),
            ))

    async def _inject_capture(self) -> None:
        if self._page:
            try:
                await self._page.evaluate(CAPTURE_SCRIPT)
            except Exception:
                pass

    async def _on_page_load(self, page: Page) -> None:
        await self._inject_capture()
        async with self._lock:
            self._events.append(RecordedEvent(
                timestamp=time.time(),
                event_type=EventType.PAGE_LOAD,
                url=page.url,
            ))

    async def _on_frame_navigated(self, frame: Any) -> None:
        if frame == self._page.main_frame:
            try:
                await self._page.evaluate(CAPTURE_SCRIPT)
            except Exception:
                pass

    async def _on_new_page(self, page: Page) -> None:
        self._page = page
        try:
            await page.expose_function("__flowtix_push", self._on_push)
        except Exception:
            pass
        page.on("load", self._on_page_load)
        page.on("framenavigated", self._on_frame_navigated)
        await page.wait_for_load_state("domcontentloaded")
        await self._inject_capture()

    async def _on_dialog(self, dialog: Any) -> None:
        async with self._lock:
            self._events.append(RecordedEvent(
                timestamp=time.time(),
                event_type=EventType.DIALOG,
                metadata={"type": dialog.type, "message": dialog.message},
            ))
        await dialog.accept()

    async def _on_file_chooser(self, chooser: Any) -> None:
        async with self._lock:
            self._events.append(RecordedEvent(
                timestamp=time.time(),
                event_type=EventType.FILE_CHOOSE,
                url=chooser.page.url,
            ))

    async def collect_events(self) -> list[RecordedEvent]:
        if self._page:
            try:
                raw = await self._page.evaluate(
                    "window.__flowtix_events ? window.__flowtix_events.splice(0) : []"
                )
                async with self._lock:
                    for item in raw:
                        self._events.append(RecordedEvent(
                            timestamp=item.get("timestamp", time.time() * 1000) / 1000,
                            event_type=item.get("event_type", "unknown"),
                            url=item.get("url", ""),
                            target=item.get("target", {}),
                            value=item.get("value"),
                            metadata=item.get("metadata", {}),
                        ))
            except Exception:
                pass
        async with self._lock:
            return list(self._events)

    async def stop(self) -> list[RecordedEvent]:
        self._running = False
        events = await self.collect_events()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        return events

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def events(self) -> list[RecordedEvent]:
        return list(self._events)
