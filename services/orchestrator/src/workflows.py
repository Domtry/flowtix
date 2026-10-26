"""Temporal workflow definitions for process execution."""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class ExecutionInput:
    execution_id: UUID
    process_id: UUID
    version_id: UUID
    robot_id: UUID
    inputs: dict
