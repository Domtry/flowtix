"""Typed message contracts between orchestrator and robots."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    # Orchestrator -> Robot
    MISSION_ASSIGN = "robot.mission.assign"
    MISSION_CANCEL = "robot.mission.cancel"
    MISSION_PAUSE = "robot.mission.pause"
    MISSION_RESUME = "robot.mission.resume"
    CONFIG_UPDATE = "robot.config.update"

    # Robot -> Orchestrator
    REGISTER = "robot.register"
    HEARTBEAT = "robot.heartbeat"
    MISSION_ACK = "robot.mission.ack"
    STEP_START = "robot.step.start"
    STEP_COMPLETE = "robot.step.complete"
    STEP_PROGRESS = "robot.step.progress"
    OBSERVATION = "robot.observation"
    ERROR = "robot.error"
    MISSION_COMPLETE = "robot.mission.complete"
    RESOURCES = "robot.resources"


class ExecutionStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    RETRYING = "retrying"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RobotStatus(str, Enum):
    ONLINE = "online"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


PROTOCOL_VERSION = "1.0"


class Message(BaseModel):
    message_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = PROTOCOL_VERSION
    type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)


class RobotCapabilities(BaseModel):
    browser: bool = False
    windows: bool = False
    ocr: bool = False
    vision: bool = False
    max_concurrent: int = 1


class RegisterPayload(BaseModel):
    robot_name: str
    machine_id: str
    capabilities: RobotCapabilities


class MissionAssignPayload(BaseModel):
    execution_id: UUID
    process_definition: dict[str, Any]
    inputs: dict[str, Any] = Field(default_factory=dict)


class StepCompletePayload(BaseModel):
    step_id: str
    success: bool
    result: Any | None = None
    error: str | None = None
    duration_ms: int = 0
    screenshot_key: str | None = None
