"""Tests for AI service facade."""

import pytest

from services.ai.src.models import AiRequest, AiTask
from services.ai.src.service import AiService


def test_select_model_default():
    svc = AiService()
    req = AiRequest(task=AiTask.CLASSIFY, prompt="test")
    assert svc._select_model(req) == "mistral:7b"


def test_select_model_vision():
    svc = AiService()
    req = AiRequest(task=AiTask.DESCRIBE_SCREEN, prompt="test", images=["base64data"])
    assert svc._select_model(req) == "llava:13b"


def test_select_model_custom():
    svc = AiService(default_model="phi3:mini")
    req = AiRequest(task=AiTask.GENERATE, prompt="test")
    assert svc._select_model(req) == "phi3:mini"


def test_ai_request_defaults():
    req = AiRequest(task=AiTask.GENERATE, prompt="hello")
    assert req.temperature == 0.1
    assert req.max_tokens == 1024
    assert req.model is None
    assert req.context == {}
