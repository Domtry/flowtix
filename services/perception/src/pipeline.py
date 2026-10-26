"""Perception pipeline — chains strategies in priority order."""

from __future__ import annotations

from typing import Any

import structlog

from .base import PerceptionProvider, PerceptionResult, PerceptionStrategy

logger = structlog.get_logger()

STRATEGY_PRIORITY = [
    PerceptionStrategy.DOM,
    PerceptionStrategy.ACCESSIBILITY,
    PerceptionStrategy.OCR,
    PerceptionStrategy.IMAGE,
    PerceptionStrategy.COORDINATES,
]


class PerceptionPipeline:
    """Tries providers in priority order until one finds the element."""

    def __init__(self, providers: list[PerceptionProvider] | None = None) -> None:
        self._providers: dict[PerceptionStrategy, PerceptionProvider] = {}
        for p in (providers or []):
            self._providers[p.strategy] = p

    def register(self, provider: PerceptionProvider) -> None:
        self._providers[provider.strategy] = provider

    async def locate(self, target: dict) -> PerceptionResult:
        strategy = target.get("strategy")
        if strategy:
            provider = self._providers.get(PerceptionStrategy(strategy))
            if provider:
                result = await provider.locate(target)
                if result.found:
                    return result

        for strat in STRATEGY_PRIORITY:
            if strat.value == strategy:
                continue
            provider = self._providers.get(strat)
            if not provider:
                continue
            result = await provider.locate(target)
            if result.found:
                logger.info("perception.found", strategy=strat.value)
                return result

        fallback = target.get("fallback")
        if fallback:
            logger.info("perception.fallback")
            return await self.locate(fallback)

        coords = target.get("coordinates")
        if coords:
            return PerceptionResult(
                strategy=PerceptionStrategy.COORDINATES,
                found=True,
                location=coords,
                confidence=0.3,
            )

        return PerceptionResult(strategy=PerceptionStrategy.COORDINATES, found=False)

    async def extract_text(self, region: dict[str, int] | None = None) -> str:
        ocr_provider = self._providers.get(PerceptionStrategy.OCR)
        if not ocr_provider:
            raise RuntimeError("No OCR provider registered")
        from .capture import capture_screen
        image = capture_screen(region)
        from .ocr import OcrProvider
        if isinstance(ocr_provider, OcrProvider):
            return ocr_provider.extract_all_text(image)
        raise RuntimeError("OCR provider does not support text extraction")
