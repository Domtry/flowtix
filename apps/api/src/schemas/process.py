from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


# --- Process ---

class ProcessCreate(BaseModel):
    name: str
    description: str | None = None
    robot_code: str | None = None


class ProcessUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    robot_code: str | None = None


class ProcessRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: str | None
    robot_code: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Process Version ---

class VersionCreate(BaseModel):
    definition: dict[str, Any]


class VersionUpdate(BaseModel):
    definition: dict[str, Any] | None = None
    status: str | None = None


class VersionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    process_id: UUID
    version: int
    schema_version: str
    definition: dict[str, Any]
    status: str
    created_at: datetime


# --- Execution ---

class ExecutionCreate(BaseModel):
    version_id: UUID
    inputs: dict[str, Any] | None = None


class ExecutionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    process_id: UUID
    version_id: UUID
    robot_id: UUID | None
    status: str
    current_step_id: str | None
    inputs: dict[str, Any] | None
    outputs: dict[str, Any] | None
    error: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ExecutionStepRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    execution_id: UUID
    step_id: str
    step_index: int
    status: str
    attempt: int
    result: dict[str, Any] | None
    error: dict[str, Any] | None
    screenshot_key: str | None
    started_at: datetime | None
    completed_at: datetime | None


# --- Robot ---

class RobotRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    machine_id: str | None
    capabilities: dict[str, Any]
    status: str
    last_heartbeat: datetime | None
    registered_at: datetime


# --- Settings ---

class SettingsRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    key: str
    value: str


class SettingsUpdate(BaseModel):
    value: str


# --- User ---

class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str = "operator"


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    email: str
    name: str
    role: str
    created_at: datetime


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead
