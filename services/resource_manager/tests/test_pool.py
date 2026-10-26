"""Tests for robot pool manager."""

import time
import pytest

from services.resource_manager.src.pool import RobotPool, RobotState


def test_register_and_list():
    pool = RobotPool()
    pool.register("r1", "Robot 1", {"browser"})
    pool.register("r2", "Robot 2", {"desktop"})
    assert len(pool.list_robots()) == 2


def test_acquire_idle():
    pool = RobotPool()
    pool.register("r1", "Robot 1", {"browser"})
    slot = pool.acquire({"browser"})
    assert slot is not None
    assert slot.robot_id == "r1"


def test_acquire_no_match():
    pool = RobotPool()
    pool.register("r1", "Robot 1", {"browser"})
    slot = pool.acquire({"desktop"})
    assert slot is None


def test_acquire_busy():
    pool = RobotPool()
    pool.register("r1", "Robot 1", max_concurrent=1)
    pool.acquire()
    slot2 = pool.acquire()
    assert slot2 is None


def test_release():
    pool = RobotPool()
    pool.register("r1", "Robot 1", max_concurrent=1)
    pool.acquire()
    pool.release("r1")
    slot = pool.acquire()
    assert slot is not None


def test_concurrent():
    pool = RobotPool()
    pool.register("r1", "Robot 1", max_concurrent=3)
    s1 = pool.acquire()
    s2 = pool.acquire()
    s3 = pool.acquire()
    assert s1 and s2 and s3
    s4 = pool.acquire()
    assert s4 is None


def test_heartbeat_recovers_offline():
    pool = RobotPool(heartbeat_timeout=0.01)
    pool.register("r1", "Robot 1")
    time.sleep(0.02)
    pool._check_timeouts()
    robots = pool.list_robots()
    assert robots[0].state == RobotState.OFFLINE
    pool.heartbeat("r1")
    assert pool.list_robots()[0].state == RobotState.IDLE


def test_unregister():
    pool = RobotPool()
    pool.register("r1", "Robot 1")
    pool.unregister("r1")
    assert len(pool.list_robots()) == 0


def test_stats():
    pool = RobotPool()
    pool.register("r1", "Robot 1")
    pool.register("r2", "Robot 2")
    pool.acquire()
    stats = pool.get_stats()
    assert stats["total"] == 2


def test_set_error():
    pool = RobotPool()
    pool.register("r1", "Robot 1")
    pool.set_error("r1", "crash")
    assert pool.list_robots()[0].state == RobotState.ERROR
