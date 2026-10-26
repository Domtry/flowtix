"""Tests for Windows element locators — unit tests without real UI."""

import pytest

from agents.windows.src.locators import locate_element, LocatorResult


def test_coordinates_fallback():
    target = {"coordinates": {"x": 100, "y": 200}}
    result = locate_element(target)
    assert result.strategy == "coordinates"
    assert result.control == {"x": 100, "y": 200}
    assert result.confidence == 0.3


def test_no_locator_raises():
    with pytest.raises(ValueError, match="Cannot locate"):
        locate_element({})


def test_fallback_chain():
    target = {
        "strategy": "dom",
        "selector": "#missing",
        "fallback": {"coordinates": {"x": 50, "y": 50}},
    }
    result = locate_element(target, window=None)
    assert result.strategy == "coordinates"
