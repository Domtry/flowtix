"""Tests for the replay engine — variable resolution and step mapping."""

from agents.browser.src.replay import ReplayEngine


def test_resolve_vars_simple():
    engine = ReplayEngine()
    result = engine._resolve_vars("Hello ${inputs.name}", {"name": "World"})
    assert result == "Hello World"


def test_resolve_vars_missing_keeps_original():
    engine = ReplayEngine()
    result = engine._resolve_vars("${inputs.missing}", {})
    assert result == "${inputs.missing}"


def test_resolve_vars_multiple():
    engine = ReplayEngine()
    result = engine._resolve_vars("${inputs.a} and ${inputs.b}", {"a": "X", "b": "Y"})
    assert result == "X and Y"


def test_resolve_non_input_var():
    engine = ReplayEngine()
    result = engine._resolve_vars("${config.url}", {})
    assert result == "${config.url}"
