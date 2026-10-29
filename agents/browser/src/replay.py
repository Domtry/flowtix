"""Playwright-based replay engine.

Takes a process definition (schema v1.0) and replays each step in a browser.
Uses a multi-strategy locator with fallback chain:
  CSS selector → aria-label → role+name → text content → coordinates.
"""

import re
import time
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Page, async_playwright


@dataclass
class StepResult:
    step_id: str
    success: bool
    duration_ms: int = 0
    error: str | None = None
    screenshot: bytes | None = None


@dataclass
class ReplayResult:
    success: bool
    steps: list[StepResult] = field(default_factory=list)
    duration_ms: int = 0


class ReplayEngine:
    def __init__(self, headless: bool = True, slow_mo: int = 0, executable_path: str = "") -> None:
        self._headless = headless
        self._slow_mo = slow_mo
        self._executable_path = executable_path

    @staticmethod
    def _detect_browser_type(path: str) -> tuple[str, str]:
        import os
        pw_firefox = os.path.expanduser(
            r"~\AppData\Local\ms-playwright\firefox-1555\firefox\firefox.exe"
        )
        lower = path.lower()
        if "firefox" in lower:
            return "firefox", pw_firefox
        if "webkit" in lower or "safari" in lower:
            return "webkit", ""
        return "chromium", path

    async def replay(
        self,
        definition: dict,
        inputs: dict[str, Any] | None = None,
        on_step: Any = None,
    ) -> ReplayResult:
        inputs = inputs or {}
        process = definition.get("process", definition)
        steps = process.get("steps", [])

        pw = await async_playwright().start()
        engine_name, effective_path = self._detect_browser_type(self._executable_path)
        launch_opts: dict[str, Any] = {"headless": self._headless, "slow_mo": self._slow_mo}
        if effective_path:
            launch_opts["executable_path"] = effective_path
        engine = getattr(pw, engine_name)
        browser = await engine.launch(**launch_opts)
        context = await browser.new_context()
        page = await context.new_page()

        results: list[StepResult] = []
        overall_start = time.monotonic()
        success = True

        for step in steps:
            step_id = step.get("id", "unknown")
            start = time.monotonic()
            try:
                await self._execute_step(page, step, inputs)
                duration = int((time.monotonic() - start) * 1000)
                result = StepResult(step_id=step_id, success=True, duration_ms=duration)
            except Exception as exc:
                duration = int((time.monotonic() - start) * 1000)
                screenshot = None
                try:
                    screenshot = await page.screenshot(full_page=False)
                except Exception:
                    pass
                result = StepResult(
                    step_id=step_id,
                    success=False,
                    duration_ms=duration,
                    error=str(exc),
                    screenshot=screenshot,
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
        await browser.close()
        await pw.stop()

        return ReplayResult(success=success, steps=results, duration_ms=total_duration)

    async def _execute_step(self, page: Page, step: dict, inputs: dict) -> None:
        step_type = step.get("type", "")
        params = step.get("params", {}) or {}
        target = step.get("target", {}) or {}
        value = step.get("value")
        timeout = step.get("timeout_ms", 30000) or 30000

        value = self._resolve_vars(value, inputs) if isinstance(value, str) else value
        for k, v in params.items():
            if isinstance(v, str):
                params[k] = self._resolve_vars(v, inputs)

        match step_type:
            case "browser.navigate":
                url = params.get("url", "")
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

            case "browser.wait":
                event = params.get("event", "load")
                if event == "load":
                    await page.wait_for_load_state("load", timeout=timeout)
                else:
                    await page.wait_for_load_state("domcontentloaded", timeout=timeout)

            case "ui.click":
                locator = await self._resolve_locator(page, target, timeout)
                if locator:
                    await locator.click(timeout=timeout)

            case "ui.dblclick":
                locator = await self._resolve_locator(page, target, timeout)
                if locator:
                    await locator.dblclick(timeout=timeout)

            case "ui.fill":
                locator = await self._resolve_locator(page, target, timeout)
                if locator:
                    await locator.fill(value or "", timeout=timeout)

            case "ui.select":
                locator = await self._resolve_locator(page, target, timeout)
                if locator:
                    await locator.select_option(value=value, timeout=timeout)

            case "ui.scroll":
                x = params.get("x", 0)
                y = params.get("y", 0)
                await page.evaluate(f"window.scrollTo({x}, {y})")

            case "keyboard.press":
                key = params.get("key", "")
                await page.keyboard.press(key)

            case "browser.dialog":
                pass

            case "assertion":
                await self._run_assertion(page, step, timeout)

            case _:
                raise ValueError(f"Unknown step type: {step_type}")

    async def _resolve_locator(self, page: Page, target: dict, timeout: int) -> Any:
        """Multi-strategy locator with fallback chain."""
        selector = target.get("selector", "")
        text = target.get("text", "")
        role = target.get("role", "")
        name = target.get("name", "") or target.get("ariaLabel", "")
        aria_label = target.get("ariaLabel", "")
        coordinates = target.get("coordinates")
        tag = target.get("tag", "")
        probe_timeout = min(timeout, 3000)

        # Strategy 1: CSS selector
        if selector:
            loc = page.locator(selector).first
            try:
                await loc.wait_for(state="attached", timeout=probe_timeout)
                return loc
            except Exception:
                pass

        # Strategy 2: aria-label
        if aria_label:
            loc = page.locator(f'[aria-label="{aria_label}"]').first
            try:
                await loc.wait_for(state="attached", timeout=probe_timeout)
                return loc
            except Exception:
                pass

        # Strategy 3: role + accessible name
        if role:
            loc = page.get_by_role(role, name=name or None).first
            try:
                await loc.wait_for(state="attached", timeout=probe_timeout)
                return loc
            except Exception:
                pass

        # Strategy 4: placeholder (for inputs)
        placeholder = target.get("placeholder", "")
        if placeholder:
            loc = page.get_by_placeholder(placeholder).first
            try:
                await loc.wait_for(state="attached", timeout=probe_timeout)
                return loc
            except Exception:
                pass

        # Strategy 5: text content (short texts only)
        if text and len(text) < 80:
            loc = page.get_by_text(text, exact=False).first
            try:
                await loc.wait_for(state="attached", timeout=probe_timeout)
                return loc
            except Exception:
                pass

        # Strategy 6: tag + text for links/buttons
        if tag in ("a", "button") and text:
            loc = page.locator(f"{tag}:has-text('{text[:50]}')").first
            try:
                await loc.wait_for(state="attached", timeout=probe_timeout)
                return loc
            except Exception:
                pass

        # Strategy 7: coordinates as last resort
        if coordinates and coordinates.get("w") and coordinates.get("h"):
            x = coordinates["x"] + coordinates["w"] // 2
            y = coordinates["y"] + coordinates["h"] // 2
            await page.mouse.click(x, y)
            return None  # Already clicked

        # Final fallback: try selector without wait
        if selector:
            return page.locator(selector).first

        raise ValueError(f"Cannot locate element: {target}")

    async def _run_assertion(self, page: Page, step: dict, timeout: int) -> None:
        conditions = step.get("postconditions", []) or step.get("preconditions", []) or []
        if not conditions and step.get("params"):
            conditions = [step["params"]]

        from playwright.async_api import expect

        for cond in conditions:
            cond_type = cond.get("type", "")
            expected = cond.get("expected", "")
            target = cond.get("target")

            match cond_type:
                case "text_contains":
                    if target:
                        loc = (await self._resolve_locator(page, target, timeout)) or page.locator("body")
                        await expect(loc).to_contain_text(str(expected), timeout=timeout)
                    else:
                        await expect(page.locator("body")).to_contain_text(str(expected), timeout=timeout)
                case "text_equals":
                    loc = (await self._resolve_locator(page, target, timeout)) if target else page.locator("body")
                    if loc:
                        await expect(loc).to_have_text(str(expected), timeout=timeout)
                case "element_visible":
                    loc = (await self._resolve_locator(page, target, timeout)) if target else page.locator(str(expected))
                    if loc:
                        await expect(loc).to_be_visible(timeout=timeout)
                case "url_matches":
                    await expect(page).to_have_url(str(expected), timeout=timeout)

    @staticmethod
    def _resolve_vars(text: str, inputs: dict) -> str:
        def replacer(m: re.Match) -> str:
            var_path = m.group(1)
            parts = var_path.split(".", 1)  # column names may themselves contain dots
            if parts[0] == "inputs" and len(parts) > 1:
                return str(inputs.get(parts[1], m.group(0)))
            return m.group(0)
        return re.sub(r"\$\{([^}]+)\}", replacer, text)
