"""Pydantic models for the FlowtTix process schema v1.0."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TargetStrategy(str, Enum):
    DOM = "dom"
    ACCESSIBILITY = "accessibility"
    OCR = "ocr"
    IMAGE = "image"
    COORDINATES = "coordinates"
    API = "api"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BackoffStrategy(str, Enum):
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class ErrorAction(str, Enum):
    FAIL = "fail"
    SKIP = "skip"
    RETRY = "retry"
    FALLBACK = "fallback"
    PAUSE = "pause"


class Target(BaseModel):
    strategy: TargetStrategy
    selector: str | None = None
    role: str | None = None
    name: str | None = None
    text: str | None = None
    image_ref: str | None = None
    coordinates: dict[str, int] | None = None
    fallback: "Target | None" = None


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=1, ge=1)
    delay_ms: int = Field(default=0, ge=0)
    backoff: BackoffStrategy = BackoffStrategy.FIXED


class ErrorStrategy(BaseModel):
    action: ErrorAction = ErrorAction.FAIL
    fallback_step: str | None = None
    notify: bool = False


class AssertionType(str, Enum):
    TEXT_EQUALS = "text_equals"
    TEXT_CONTAINS = "text_contains"
    ELEMENT_VISIBLE = "element_visible"
    ELEMENT_ENABLED = "element_enabled"
    VALUE_MATCHES = "value_matches"
    URL_MATCHES = "url_matches"
    CUSTOM = "custom"


class Assertion(BaseModel):
    type: AssertionType
    target: Target | None = None
    expected: Any
    timeout_ms: int | None = None


class Step(BaseModel):
    id: str
    type: str
    label: str | None = None
    target: Target | None = None
    params: dict[str, Any] | None = None
    value: Any | None = None
    preconditions: list[Assertion] = Field(default_factory=list)
    postconditions: list[Assertion] = Field(default_factory=list)
    timeout_ms: int | None = None
    retry: RetryPolicy | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    on_error: ErrorStrategy | None = None


class DataStepParams(BaseModel):
    """Parameters for data.extract / data.transform / data.validate / data.load steps."""
    source: str | None = None
    destination: str | None = None
    format: str | None = None
    data: Any | None = None
    output_variable: str | None = None
    operations: list[dict[str, Any]] = Field(default_factory=list)
    rules: list[dict[str, Any]] = Field(default_factory=list)
    csv_options: dict[str, Any] | None = None
    excel_options: dict[str, Any] | None = None
    json_options: dict[str, Any] | None = None
    xml_options: dict[str, Any] | None = None


class VariableDefinition(BaseModel):
    type: str = "string"
    required: bool = False
    default: Any | None = None
    sensitive: bool = False


class ProcessDefinition(BaseModel):
    id: str
    name: str
    description: str | None = None
    inputs: dict[str, VariableDefinition] = Field(default_factory=dict)
    outputs: dict[str, VariableDefinition] = Field(default_factory=dict)
    steps: list[Step]
    error_strategy: ErrorStrategy | None = None
    timeout_ms: int | None = None


class ProcessDocument(BaseModel):
    schema_version: str = "1.0"
    process: ProcessDefinition
