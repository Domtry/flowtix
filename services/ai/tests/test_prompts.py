"""Tests for prompt template builder."""

from services.ai.src.models import AiTask
from services.ai.src.prompts import build_prompt


def test_classify_prompt():
    result = build_prompt(AiTask.CLASSIFY, {"data": "Click me", "categories": "button, link, text"})
    assert "button, link, text" in result
    assert "Click me" in result


def test_extract_prompt():
    result = build_prompt(AiTask.EXTRACT, {"data": "John Doe, age 30", "fields": "name, age"})
    assert "name, age" in result


def test_summarize_prompt():
    result = build_prompt(AiTask.SUMMARIZE, {"data": "Long text...", "max_length": "50"})
    assert "50" in result


def test_repair_selector_prompt():
    result = build_prompt(AiTask.REPAIR_SELECTOR, {"selector": "#old-btn", "html": "<button id='new-btn'>"})
    assert "#old-btn" in result
    assert "new-btn" in result


def test_generate_passthrough():
    result = build_prompt(AiTask.GENERATE, {"prompt": "Do something custom"})
    assert result == "Do something custom"


def test_decide_prompt():
    result = build_prompt(AiTask.DECIDE, {"context": "Page loaded", "actions": "click, wait, scroll"})
    assert "click, wait, scroll" in result


def test_missing_keys_fallback():
    result = build_prompt(AiTask.CLASSIFY, {"prompt": "fallback text"})
    assert result == "fallback text"
