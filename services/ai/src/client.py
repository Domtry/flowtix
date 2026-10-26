"""Ollama HTTP client — wraps the Ollama REST API."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from .models import ChatMessage, ModelInfo, OllamaChatRequest, OllamaGenerateRequest

logger = structlog.get_logger()

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaClient:
    """Async HTTP client for the Ollama API."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        images: list[str] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        req = OllamaGenerateRequest(
            model=model,
            prompt=prompt,
            system=system,
            images=images,
            options={"temperature": temperature, "num_predict": max_tokens},
        )
        return await self._post("/api/generate", req.model_dump(exclude_none=True))

    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        req = OllamaChatRequest(
            model=model,
            messages=[m.model_dump(exclude_none=True) for m in messages],
            options={"temperature": temperature, "num_predict": max_tokens},
        )
        return await self._post("/api/chat", req.model_dump(exclude_none=True))

    async def list_models(self) -> list[ModelInfo]:
        data = await self._get("/api/tags")
        models = []
        for m in data.get("models", []):
            details = m.get("details", {})
            models.append(ModelInfo(
                name=m.get("name", ""),
                size=m.get("size", 0),
                parameter_size=details.get("parameter_size", ""),
                quantization=details.get("quantization_level", ""),
                family=details.get("family", ""),
                modified_at=m.get("modified_at", ""),
            ))
        return models

    async def pull_model(self, model: str) -> dict[str, Any]:
        return await self._post("/api/pull", {"name": model, "stream": False})

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/")
                return resp.status_code == 200
        except Exception:
            return False

    async def _post(self, path: str, payload: dict) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}{path}", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def _get(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}{path}")
            resp.raise_for_status()
            return resp.json()
