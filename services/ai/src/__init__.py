"""FlowtTix AI Engine — local LLM via Ollama."""

from .client import OllamaClient
from .models import (
    AiRequest,
    AiResponse,
    AiTask,
    ChatMessage,
    ModelInfo,
)
from .service import AiService

__all__ = [
    "AiRequest",
    "AiResponse",
    "AiService",
    "AiTask",
    "ChatMessage",
    "ModelInfo",
    "OllamaClient",
]
