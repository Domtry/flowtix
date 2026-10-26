"""Windows robot agent — implements BaseRobotAgent for desktop automation."""

from __future__ import annotations

from packages.execution_contracts.src.messages import (
    Message,
    RobotCapabilities,
)
from agents.common.src.base import BaseRobotAgent
from .replay import WindowsReplayEngine


class WindowsAgent(BaseRobotAgent):
    def __init__(self, backend: str = "uia") -> None:
        self._engine = WindowsReplayEngine(backend=backend)

    def capabilities(self) -> RobotCapabilities:
        return RobotCapabilities(
            browser=False,
            desktop=True,
            sap=False,
            ocr=True,
            image_match=False,
        )

    async def execute_step(self, step: dict) -> dict:
        result = await self._engine.replay(
            {"process": {"id": "single", "name": "single", "steps": [step]}}
        )
        step_result = result.steps[0] if result.steps else None
        return {
            "success": result.success,
            "duration_ms": result.duration_ms,
            "error": step_result.error if step_result else None,
        }

    async def handle_message(self, message: Message) -> Message | None:
        return None
