"""Tests for perception pipeline — provider chaining and fallback."""

import asyncio

import pytest

from services.perception.src.base import PerceptionProvider, PerceptionResult, PerceptionStrategy
from services.perception.src.pipeline import PerceptionPipeline


class MockProvider(PerceptionProvider):
    def __init__(self, strategy: PerceptionStrategy, found: bool, confidence: float = 1.0):
        self.strategy = strategy
        self._found = found
        self._confidence = confidence

    async def locate(self, target: dict) -> PerceptionResult:
        return PerceptionResult(
            strategy=self.strategy,
            found=self._found,
            text=target.get("text"),
            confidence=self._confidence,
            location={"x": 100, "y": 100} if self._found else None,
        )


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_first_provider_wins():
    pipeline = PerceptionPipeline([
        MockProvider(PerceptionStrategy.OCR, found=True, confidence=0.9),
        MockProvider(PerceptionStrategy.IMAGE, found=True, confidence=0.8),
    ])
    result = _run(pipeline.locate({"strategy": "ocr", "text": "hello"}))
    assert result.found
    assert result.strategy == PerceptionStrategy.OCR


def test_fallback_to_next():
    pipeline = PerceptionPipeline([
        MockProvider(PerceptionStrategy.OCR, found=False),
        MockProvider(PerceptionStrategy.IMAGE, found=True, confidence=0.85),
    ])
    result = _run(pipeline.locate({"strategy": "ocr", "text": "hello"}))
    assert result.found
    assert result.strategy == PerceptionStrategy.IMAGE


def test_coordinates_fallback():
    pipeline = PerceptionPipeline()
    result = _run(pipeline.locate({"coordinates": {"x": 50, "y": 50}}))
    assert result.found
    assert result.strategy == PerceptionStrategy.COORDINATES


def test_nothing_found():
    pipeline = PerceptionPipeline([
        MockProvider(PerceptionStrategy.OCR, found=False),
    ])
    result = _run(pipeline.locate({"strategy": "ocr", "text": "missing"}))
    assert not result.found


def test_target_fallback_chain():
    pipeline = PerceptionPipeline([
        MockProvider(PerceptionStrategy.OCR, found=False),
    ])
    target = {
        "strategy": "ocr",
        "text": "missing",
        "fallback": {"coordinates": {"x": 10, "y": 20}},
    }
    result = _run(pipeline.locate(target))
    assert result.found
    assert result.location == {"x": 10, "y": 20}
