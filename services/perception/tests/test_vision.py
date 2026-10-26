"""Tests for image matching provider — synthetic images."""

import numpy as np
import pytest

from services.perception.src.vision import ImageMatch, ImageMatchProvider


def _make_image(w: int, h: int, color: tuple = (128, 128, 128)) -> np.ndarray:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = color
    return img


def _embed_patch(screen: np.ndarray, patch: np.ndarray, x: int, y: int) -> np.ndarray:
    h, w = patch.shape[:2]
    screen[y:y + h, x:x + w] = patch
    return screen


def test_find_template_exact():
    screen = _make_image(200, 200, (50, 50, 50))
    template = _make_image(30, 30, (200, 200, 200))
    screen = _embed_patch(screen, template, 80, 60)

    provider = ImageMatchProvider(threshold=0.9)
    match = provider.find_template(screen, template)
    assert match is not None
    assert match.confidence > 0.9
    assert abs(match.center_x - 95) < 5
    assert abs(match.center_y - 75) < 5


def test_find_template_no_match():
    screen = _make_image(200, 200, (50, 50, 50))
    template = _make_image(30, 30, (200, 200, 200))

    provider = ImageMatchProvider(threshold=0.9)
    match = provider.find_template(screen, template)
    assert match is None


def test_find_all_templates():
    screen = _make_image(300, 300, (50, 50, 50))
    template = _make_image(20, 20, (200, 200, 200))
    screen = _embed_patch(screen, template, 50, 50)
    screen = _embed_patch(screen, template, 150, 150)

    provider = ImageMatchProvider(threshold=0.9)
    matches = provider.find_all_templates(screen, template)
    assert len(matches) >= 2


def test_image_match_dataclass():
    m = ImageMatch(x=10, y=20, width=30, height=40, confidence=0.95, center_x=25, center_y=40)
    assert m.center_x == 25
