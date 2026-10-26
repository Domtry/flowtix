"""Tests for system resource monitor."""

from services.resource_manager.src.monitor import ResourceMonitor


def test_snapshot():
    monitor = ResourceMonitor()
    snap = monitor.snapshot()
    assert snap.cpu_count >= 1
    assert snap.memory_total_mb > 0
    assert snap.disk_total_gb > 0
    assert 0 <= snap.cpu_percent <= 100
    assert 0 <= snap.memory_percent <= 100


def test_can_run_robot():
    monitor = ResourceMonitor()
    result = monitor.can_run_robot(min_memory_mb=1, max_cpu_percent=100.0)
    assert result is True


def test_cannot_run_robot_low_memory():
    monitor = ResourceMonitor()
    result = monitor.can_run_robot(min_memory_mb=999999999)
    assert result is False
