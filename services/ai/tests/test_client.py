"""Tests for Ollama client — mocked HTTP."""

import pytest
import httpx
import respx

from services.ai.src.client import OllamaClient
from services.ai.src.models import ChatMessage


BASE = "http://localhost:11434"


@pytest.fixture
def client():
    return OllamaClient(base_url=BASE, timeout=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_generate(client):
    respx.post(f"{BASE}/api/generate").mock(return_value=httpx.Response(200, json={
        "response": "Hello world",
        "prompt_eval_count": 10,
        "eval_count": 5,
    }))
    result = await client.generate("mistral:7b", "Say hello")
    assert result["response"] == "Hello world"


@respx.mock
@pytest.mark.asyncio
async def test_chat(client):
    respx.post(f"{BASE}/api/chat").mock(return_value=httpx.Response(200, json={
        "message": {"role": "assistant", "content": "Hi!"},
    }))
    result = await client.chat("mistral:7b", [ChatMessage(content="Hello")])
    assert "message" in result


@respx.mock
@pytest.mark.asyncio
async def test_list_models(client):
    respx.get(f"{BASE}/api/tags").mock(return_value=httpx.Response(200, json={
        "models": [
            {"name": "mistral:7b", "size": 4000000000, "details": {"parameter_size": "7B", "family": "mistral"}},
            {"name": "llava:13b", "size": 8000000000, "details": {"parameter_size": "13B", "family": "llava"}},
        ]
    }))
    models = await client.list_models()
    assert len(models) == 2
    assert models[0].name == "mistral:7b"
    assert models[1].family == "llava"


@respx.mock
@pytest.mark.asyncio
async def test_health_ok(client):
    respx.get(f"{BASE}/").mock(return_value=httpx.Response(200))
    assert await client.health() is True


@respx.mock
@pytest.mark.asyncio
async def test_health_down(client):
    respx.get(f"{BASE}/").mock(side_effect=httpx.ConnectError("refused"))
    assert await client.health() is False
