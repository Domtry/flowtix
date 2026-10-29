"""Selenium-based browser recorder for non-Chromium browsers (Firefox, etc.).

Uses Selenium WebDriver to launch the real system browser and injects
the same capture script as the Playwright recorder.
"""

import asyncio
import json
import time
from typing import Any

import os

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

from .recorder import CAPTURE_SCRIPT, EventType, RecordedEvent

DRIVERS_DIR = os.path.expanduser(r"~\.flowtix\drivers")


def _detect_selenium_browser(path: str) -> str:
    lower = path.lower()
    if "firefox" in lower:
        return "firefox"
    if "chrome" in lower or "chromium" in lower:
        return "chrome"
    if "edge" in lower or "msedge" in lower:
        return "edge"
    return "firefox"


class SeleniumRecorder:
    def __init__(self, executable_path: str = "") -> None:
        self._executable_path = executable_path
        self._driver: webdriver.Remote | None = None
        self._events: list[RecordedEvent] = []
        self._running = False
        self._lock = asyncio.Lock()
        self._poll_task: asyncio.Task | None = None

    async def start(self, url: str) -> None:
        browser_type = _detect_selenium_browser(self._executable_path)

        loop = asyncio.get_event_loop()
        self._driver = await loop.run_in_executor(
            None, self._create_driver, browser_type
        )

        await loop.run_in_executor(None, self._driver.get, url)
        await loop.run_in_executor(None, self._driver.execute_script, CAPTURE_SCRIPT)

        self._running = True
        self._events.append(RecordedEvent(
            timestamp=time.time(),
            event_type=EventType.NAVIGATE,
            url=url,
        ))
        self._poll_task = asyncio.create_task(self._poll_events_loop())

    def _create_driver(self, browser_type: str) -> webdriver.Remote:
        if browser_type == "firefox":
            options = FirefoxOptions()
            options.binary_location = self._executable_path
            gecko = os.path.join(DRIVERS_DIR, "geckodriver.exe")
            service = FirefoxService(executable_path=gecko) if os.path.isfile(gecko) else FirefoxService()
            return webdriver.Firefox(service=service, options=options)
        elif browser_type == "edge":
            from selenium.webdriver.edge.options import Options as EdgeOptions
            from selenium.webdriver.edge.service import Service as EdgeService
            options = EdgeOptions()
            options.binary_location = self._executable_path
            return webdriver.Edge(options=options)
        else:
            options = ChromeOptions()
            options.binary_location = self._executable_path
            return webdriver.Chrome(options=options)

    async def _poll_events_loop(self) -> None:
        loop = asyncio.get_event_loop()
        while self._running:
            await asyncio.sleep(0.5)
            try:
                await self._drain_browser_events(loop)
            except Exception:
                pass

    async def _drain_browser_events(self, loop: asyncio.AbstractEventLoop) -> None:
        if not self._driver:
            return

        current_url = await loop.run_in_executor(None, lambda: self._driver.current_url)

        raw = await loop.run_in_executor(
            None,
            self._driver.execute_script,
            """
            if (!window.__flowtix_recording) return [];
            var evts = window.__flowtix_events ? window.__flowtix_events.splice(0) : [];
            return evts;
            """,
        )

        try:
            await loop.run_in_executor(
                None, self._driver.execute_script, CAPTURE_SCRIPT
            )
        except Exception:
            pass

        if not raw:
            return

        async with self._lock:
            for item in raw:
                self._events.append(RecordedEvent(
                    timestamp=item.get("timestamp", time.time() * 1000) / 1000,
                    event_type=item.get("event_type", "unknown"),
                    url=item.get("url", current_url),
                    target=item.get("target", {}),
                    value=item.get("value"),
                    metadata=item.get("metadata", {}),
                ))

    async def collect_events(self) -> list[RecordedEvent]:
        if self._driver:
            loop = asyncio.get_event_loop()
            try:
                await self._drain_browser_events(loop)
            except Exception:
                pass
        async with self._lock:
            return list(self._events)

    async def stop(self) -> list[RecordedEvent]:
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        events = await self.collect_events()

        if self._driver:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._driver.quit)
            self._driver = None

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
