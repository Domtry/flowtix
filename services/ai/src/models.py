"""AI engine models — requests, responses, task types."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AiTask(str, Enum):
    CLASSIFY = "classify"
    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    GENERATE = "generate"
    DECIDE = "decide"
    REPAIR_SELECTOR = "repair_selector"
    DESCRIBE_SCREEN = "describe_screen"


class ChatMessage(BaseModel):
    role: str = "user"
    content: str
    images: list[str] | None = None


class AiRequest(BaseModel):
    task: AiTask
    prompt: str
    context: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None
    temperature: float = 0.1
    max_tokens: int = 1024
    images: list[str] | None = None
    system_prompt: str | None = None


class AiResponse(BaseModel):
    task: AiTask
    result: str
    model: str
    usage: dict[str, int] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class ModelInfo(BaseModel):
    name: str
    size: int = 0
    parameter_size: str = ""
    quantization: str = ""
    family: str = ""
    modified_at: str = ""


class OllamaGenerateRequest(BaseModel):
    model: str
    prompt: str
    system: str | None = None
    images: list[str] | None = None
    stream: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


class OllamaChatRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    stream: bool = False
    options: dict[str, Any] = Field(default_factory=dict)
