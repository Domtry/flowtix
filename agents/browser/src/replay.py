"""Playwright-based replay engine.

Takes a process definition (schema v1.0) and replays each step in a browser.
Produces step-by-step results with screenshots on failure.
"""

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
    def __init__(self, headless: bool = True, slow_mo: int = 0) -> None:
        self._headless = headless
        self._slow_mo = slow_mo

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
        browser = await pw.chromium.launch(headless=self._headless, slow_mo=self._slow_mo)
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
                screenshot = await page.screenshot(full_page=False)
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

        # Resolve variable references
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
                locator = self._get_locator(page, target)
                await locator.click(timeout=timeout)

            case "ui.dblclick":
                locator = self._get_locator(page, target)
                await locator.dblclick(timeout=timeout)

            case "ui.fill":
                locator = self._get_locator(page, target)
                await locator.fill(value or "", timeout=timeout)

            case "ui.select":
                locator = self._get_locator(page, target)
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

    def _get_locator(self, page: Page, target: dict) -> Any:
        strategy = target.get("strategy", "dom")

        match strategy:
            case "dom":
                selector = target.get("selector", "")
                if selector:
                    return page.locator(selector).first
            case "accessibility":
                role = target.get("role", "")
                name = target.get("name", "")
                if role:
                    return page.get_by_role(role, name=name or None)
            case "ocr" | "image":
                text = target.get("text", "")
                if text:
                    return page.get_by_text(text).first

        # Fallback chain
        if target.get("text"):
            return page.get_by_text(target["text"]).first
        if target.get("role"):
            return page.get_by_role(target["role"], name=target.get("name") or None)
        if target.get("selector"):
            return page.locator(target["selector"]).first

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
                        loc = self._get_locator(page, target)
                        await expect(loc).to_contain_text(str(expected), timeout=timeout)
                    else:
                        await expect(page.locator("body")).to_contain_text(str(expected), timeout=timeout)
                case "text_equals":
                    loc = self._get_locator(page, target) if target else page.locator("body")
                    await expect(loc).to_have_text(str(expected), timeout=timeout)
                case "element_visible":
                    loc = self._get_locator(page, target) if target else page.locator(str(expected))
                    await expect(loc).to_be_visible(timeout=timeout)
                case "url_matches":
                    await expect(page).to_have_url(str(expected), timeout=timeout)

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
