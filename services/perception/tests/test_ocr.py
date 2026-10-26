"""Tests for OCR provider — unit tests with synthetic images."""

import numpy as np
import pytest

from services.perception.src.ocr import OcrMatch, OcrProvider


def test_ocr_match_dataclass():
    m = OcrMatch(text="Hello", confidence=0.95, bbox=[[0, 0], [100, 0], [100, 30], [0, 30]], center_x=50, center_y=15)
    assert m.text == "Hello"
    assert m.confidence == 0.95
    assert m.center_x == 50


def test_ocr_provider_no_text():
    """locate with empty text returns not found."""
    provider = OcrProvider(engine="auto")
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        provider.locate({"text": ""})
    )
    assert not result.found


def test_ocr_provider_with_image_no_engine():
    """When no engine is available, init raises."""
    provider = OcrProvider(engine="auto")
    provider._engine = "nonexistent"
    with pytest.raises(RuntimeError, match="No OCR engine"):
        provider._init_engine()
