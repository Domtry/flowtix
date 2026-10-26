"""Tests for Windows replay engine — variable resolution (no real UI)."""

from agents.windows.src.replay import WindowsReplayEngine


def test_resolve_vars_simple():
    result = WindowsReplayEngine._resolve_vars("Hello ${inputs.name}", {"name": "Alice"})
    assert result == "Hello Alice"


def test_resolve_vars_missing():
    result = WindowsReplayEngine._resolve_vars("${inputs.x}", {})
    assert result == "${inputs.x}"


def test_resolve_vars_multiple():
    result = WindowsReplayEngine._resolve_vars(
        "${inputs.a} and ${inputs.b}", {"a": "1", "b": "2"}
    )
    assert result == "1 and 2"
