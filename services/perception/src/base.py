"""Base perception interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class PerceptionStrategy(str, Enum):
    DOM = "dom"
    ACCESSIBILITY = "accessibility"
    OCR = "ocr"
    IMAGE = "image"
    COORDINATES = "coordinates"
    API = "api"


@dataclass
class PerceptionResult:
    strategy: PerceptionStrategy
    found: bool
    text: str | None = None
    element_type: str | None = None
    location: dict | None = None
    properties: dict | None = None
    confidence: float = 1.0


class PerceptionProvider(ABC):
    strategy: PerceptionStrategy

    @abstractmethod
    async def locate(self, target: dict) -> PerceptionResult: ...
