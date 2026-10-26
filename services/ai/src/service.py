"""AI service facade — dispatches AI tasks to Ollama."""

from __future__ import annotations

from typing import Any

import structlog

from .client import OllamaClient
from .models import AiRequest, AiResponse, AiTask, ChatMessage, ModelInfo
from .prompts import SYSTEM_PROMPT, build_prompt

logger = structlog.get_logger()

DEFAULT_MODEL = "mistral:7b"
VISION_MODEL = "llava:13b"


class AiService:
    """High-level AI service for RPA tasks."""

    def __init__(
        self,
        client: OllamaClient | None = None,
        default_model: str = DEFAULT_MODEL,
        vision_model: str = VISION_MODEL,
    ) -> None:
        self._client = client or OllamaClient()
        self._default_model = default_model
        self._vision_model = vision_model

    async def execute(self, request: AiRequest) -> AiResponse:
        model = request.model or self._select_model(request)
        prompt = request.prompt or build_prompt(request.task, request.context)
        system = request.system_prompt or SYSTEM_PROMPT

        logger.info("ai.execute", task=request.task, model=model)

        result = await self._client.generate(
            model=model,
            prompt=prompt,
            system=system,
            images=request.images,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        return AiResponse(
            task=request.task,
            result=result.get("response", ""),
            model=model,
            usage={
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "completion_tokens": result.get("eval_count", 0),
            },
            raw=result,
        )

    async def classify(self, data: str, categories: list[str], **kwargs: Any) -> AiResponse:
        return await self.execute(AiRequest(
            task=AiTask.CLASSIFY,
            prompt="",
            context={"data": data, "categories": ", ".join(categories)},
            **kwargs,
        ))

    async def extract(self, data: str, fields: list[str], **kwargs: Any) -> AiResponse:
        return await self.execute(AiRequest(
            task=AiTask.EXTRACT,
            prompt="",
            context={"data": data, "fields": ", ".join(fields)},
            **kwargs,
        ))

    async def summarize(self, data: str, max_length: int = 100, **kwargs: Any) -> AiResponse:
        return await self.execute(AiRequest(
            task=AiTask.SUMMARIZE,
            prompt="",
            context={"data": data, "max_length": str(max_length)},
            **kwargs,
        ))

    async def repair_selector(self, selector: str, html: str, **kwargs: Any) -> AiResponse:
        return await self.execute(AiRequest(
            task=AiTask.REPAIR_SELECTOR,
            prompt="",
            context={"selector": selector, "html": html},
            **kwargs,
        ))

    async def describe_screen(self, image_b64: str, **kwargs: Any) -> AiResponse:
        return await self.execute(AiRequest(
            task=AiTask.DESCRIBE_SCREEN,
            prompt="",
            images=[image_b64],
            model=self._vision_model,
            **kwargs,
        ))

    async def decide(self, context: str, actions: list[str], **kwargs: Any) -> AiResponse:
        return await self.execute(AiRequest(
            task=AiTask.DECIDE,
            prompt="",
            context={"context": context, "actions": ", ".join(actions)},
            **kwargs,
        ))

    async def list_models(self) -> list[ModelInfo]:
        return await self._client.list_models()

    async def health(self) -> bool:
        return await self._client.health()

    def _select_model(self, request: AiRequest) -> str:
        if request.images:
            return self._vision_model
        return self._default_model
