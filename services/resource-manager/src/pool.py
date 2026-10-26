"""Robot pool manager — multi-robot scheduling and assignment."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class RobotState(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class RobotSlot:
    robot_id: str
    name: str
    state: RobotState = RobotState.OFFLINE
    capabilities: set[str] = field(default_factory=set)
    current_execution_id: str | None = None
    last_heartbeat: float = 0
    max_concurrent: int = 1
    active_count: int = 0
    tags: dict[str, str] = field(default_factory=dict)


class RobotPool:
    """Manages a pool of robots for execution assignment."""

    def __init__(self, heartbeat_timeout: float = 60.0) -> None:
        self._robots: dict[str, RobotSlot] = {}
        self._heartbeat_timeout = heartbeat_timeout

    def register(self, robot_id: str, name: str, capabilities: set[str] | None = None, max_concurrent: int = 1) -> RobotSlot:
        slot = RobotSlot(
            robot_id=robot_id,
            name=name,
            state=RobotState.IDLE,
            capabilities=capabilities or set(),
            last_heartbeat=time.monotonic(),
            max_concurrent=max_concurrent,
        )
        self._robots[robot_id] = slot
        logger.info("pool.register", robot=robot_id, name=name)
        return slot

    def unregister(self, robot_id: str) -> None:
        self._robots.pop(robot_id, None)
        logger.info("pool.unregister", robot=robot_id)

    def heartbeat(self, robot_id: str) -> None:
        slot = self._robots.get(robot_id)
        if slot:
            slot.last_heartbeat = time.monotonic()
            if slot.state == RobotState.OFFLINE:
                slot.state = RobotState.IDLE

    def acquire(self, required_capabilities: set[str] | None = None) -> RobotSlot | None:
        """Find and reserve an available robot matching capabilities."""
        self._check_timeouts()
        candidates = [
            s for s in self._robots.values()
            if s.state == RobotState.IDLE
            and s.active_count < s.max_concurrent
            and (not required_capabilities or required_capabilities.issubset(s.capabilities))
        ]
        if not candidates:
            return None

        slot = min(candidates, key=lambda s: s.active_count)
        slot.active_count += 1
        if slot.active_count >= slot.max_concurrent:
            slot.state = RobotState.BUSY
        logger.info("pool.acquire", robot=slot.robot_id)
        return slot

    def release(self, robot_id: str) -> None:
        slot = self._robots.get(robot_id)
        if slot:
            slot.active_count = max(0, slot.active_count - 1)
            slot.current_execution_id = None
            if slot.state == RobotState.BUSY and slot.active_count < slot.max_concurrent:
                slot.state = RobotState.IDLE
            logger.info("pool.release", robot=robot_id)

    def set_error(self, robot_id: str, reason: str = "") -> None:
        slot = self._robots.get(robot_id)
        if slot:
            slot.state = RobotState.ERROR
            logger.warning("pool.error", robot=robot_id, reason=reason)

    def list_robots(self) -> list[RobotSlot]:
        self._check_timeouts()
        return list(self._robots.values())

    def get_stats(self) -> dict[str, int]:
        self._check_timeouts()
        stats: dict[str, int] = {}
        for slot in self._robots.values():
            stats[slot.state.value] = stats.get(slot.state.value, 0) + 1
        stats["total"] = len(self._robots)
        return stats

    def _check_timeouts(self) -> None:
        now = time.monotonic()
        for slot in self._robots.values():
            if slot.state != RobotState.OFFLINE and (now - slot.last_heartbeat) > self._heartbeat_timeout:
                slot.state = RobotState.OFFLINE
                slot.active_count = 0
                logger.warning("pool.timeout", robot=slot.robot_id)
