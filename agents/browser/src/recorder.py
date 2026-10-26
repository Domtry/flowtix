"""Browser recorder — captures user actions via Playwright CDP instrumentation.

Launches a headed browser, injects event listeners, and collects structured
events that the transformer will convert into a process scenario.
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

    function getSelector(el) {
        if (el.id) return '#' + CSS.escape(el.id);
        if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
        if (el.getAttribute && el.getAttribute('data-testid'))
            return '[data-testid="' + el.getAttribute('data-testid') + '"]';

        // Build a CSS selector from tag + classes
        let sel = el.tagName.toLowerCase();
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.trim().split(/\\s+/).slice(0, 3);
            if (classes.length && classes[0]) sel += '.' + classes.map(CSS.escape).join('.');
        }
        return sel;
    }

    function getTarget(el) {
        return {
            tag: el.tagName ? el.tagName.toLowerCase() : '',
            selector: getSelector(el),
            text: (el.innerText || '').slice(0, 200),
            type: el.type || '',
            name: el.name || '',
            role: el.getAttribute ? (el.getAttribute('role') || '') : '',
            ariaLabel: el.getAttribute ? (el.getAttribute('aria-label') || '') : '',
            rect: el.getBoundingClientRect ? (() => {
                const r = el.getBoundingClientRect();
                return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};
            })() : null,
        };
    }

    function push(eventType, el, extra) {
        window.__flowtix_events.push({
            timestamp: Date.now(),
            event_type: eventType,
            url: location.href,
            target: el ? getTarget(el) : {},
            ...extra,
        });
    }

    document.addEventListener('click', e => push('click', e.target, {}), true);
    document.addEventListener('dblclick', e => push('dblclick', e.target, {}), true);
    document.addEventListener('contextmenu', e => push('contextmenu', e.target, {}), true);

    // Debounced input capture
    let inputTimer = null;
    document.addEventListener('input', e => {
        clearTimeout(inputTimer);
        const el = e.target;
        inputTimer = setTimeout(() => {
            push('input', el, {value: el.value || ''});
        }, 300);
    }, true);

    document.addEventListener('change', e => {
        push('change', e.target, {value: e.target.value || ''});
    }, true);

    document.addEventListener('keydown', e => {
        if (e.key === 'Tab' || e.key === 'Enter' || e.key === 'Escape' ||
            (e.ctrlKey && e.key.length === 1) || (e.altKey && e.key.length === 1)) {
            push('keydown', e.target, {metadata: {key: e.key, ctrl: e.ctrlKey, alt: e.altKey, shift: e.shiftKey}});
        }
    }, true);

    let scrollTimer = null;
    window.addEventListener('scroll', () => {
        clearTimeout(scrollTimer);
        scrollTimer = setTimeout(() => {
            push('scroll', document.scrollingElement, {
                metadata: {scrollX: window.scrollX, scrollY: window.scrollY}
            });
        }, 500);
    }, true);
})();
"""


class BrowserRecorder:
    def __init__(self) -> None:
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._events: list[RecordedEvent] = []
        self._running = False

    async def start(self, url: str) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=False)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()

        self._page.on("load", self._on_page_load)
        self._page.on("dialog", self._on_dialog)
        self._page.on("filechooser", self._on_file_chooser)

        self._context.on("page", self._on_new_page)

        await self._page.goto(url, wait_until="domcontentloaded")
        await self._inject_capture()

        self._running = True
        self._events.append(RecordedEvent(
            timestamp=time.time(),
            event_type=EventType.NAVIGATE,
            url=url,
        ))

    async def _inject_capture(self) -> None:
        if self._page:
            await self._page.evaluate(CAPTURE_SCRIPT)

    async def _on_page_load(self, page: Page) -> None:
        await page.evaluate(CAPTURE_SCRIPT)
        self._events.append(RecordedEvent(
            timestamp=time.time(),
            event_type=EventType.PAGE_LOAD,
            url=page.url,
        ))

    async def _on_new_page(self, page: Page) -> None:
        self._page = page
        page.on("load", self._on_page_load)
        await page.wait_for_load_state("domcontentloaded")
        await page.evaluate(CAPTURE_SCRIPT)

    async def _on_dialog(self, dialog: Any) -> None:
        self._events.append(RecordedEvent(
            timestamp=time.time(),
            event_type=EventType.DIALOG,
            metadata={"type": dialog.type, "message": dialog.message},
        ))
        await dialog.accept()

    async def _on_file_chooser(self, chooser: Any) -> None:
        self._events.append(RecordedEvent(
            timestamp=time.time(),
            event_type=EventType.FILE_CHOOSE,
            url=chooser.page.url,
        ))

    async def collect_events(self) -> list[RecordedEvent]:
        if not self._page:
            return []
        raw = await self._page.evaluate("window.__flowtix_events ? window.__flowtix_events.splice(0) : []")
        for item in raw:
            self._events.append(RecordedEvent(
                timestamp=item.get("timestamp", time.time()) / 1000,
                event_type=item.get("event_type", "unknown"),
                url=item.get("url", ""),
                target=item.get("target", {}),
                value=item.get("value"),
                metadata=item.get("metadata", {}),
            ))
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
