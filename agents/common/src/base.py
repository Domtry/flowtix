"""Base robot agent interface."""

from abc import ABC, abstractmethod

from packages.execution_contracts.src.messages import (
    Message,
    RobotCapabilities,
)


class BaseRobotAgent(ABC):
    @abstractmethod
    def capabilities(self) -> RobotCapabilities: ...

    @abstractmethod
    async def execute_step(self, step: dict) -> dict: ...

    @abstractmethod
    async def handle_message(self, message: Message) -> Message | None: ...
