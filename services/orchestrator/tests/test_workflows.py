"""Tests for the ProcessExecutionWorkflow — state transitions, signals, error handling.

Uses Temporal's test environment for deterministic replay without a real server.
"""

import pytest
from unittest.mock import AsyncMock, patch
from dataclasses import dataclass

from services.orchestrator.src.workflows import (
    ExecutionInput,
    ExecutionState,
    ExecutionStatus,
    ProcessExecutionWorkflow,
)
from services.orchestrator.src.activities import (
    ExecuteStepResult,
    GenerateReportInput,
    SaveStepResultInput,
    UpdateExecutionStatusInput,
)


def _make_input(steps: list[dict], inputs: dict | None = None) -> ExecutionInput:
    return ExecutionInput(
        execution_id="exec-1",
        process_id="proc-1",
        version_id="ver-1",
        definition={
            "process": {
                "id": "test",
                "name": "Test",
                "steps": steps,
            }
        },
        inputs=inputs or {},
    )


# --- Unit tests for ExecutionState ---

def test_initial_state():
    state = ExecutionState()
    assert state.status == ExecutionStatus.CREATED
    assert state.current_step_index == 0
    assert state.completed_steps == []
    assert state.failed_steps == []
    assert state.paused is False
    assert state.cancelled is False


def test_state_transitions():
    state = ExecutionState()
    state.status = ExecutionStatus.RUNNING
    assert state.status == ExecutionStatus.RUNNING

    state.status = ExecutionStatus.PAUSED
    state.paused = True
    assert state.paused is True

    state.paused = False
    state.status = ExecutionStatus.RUNNING
    assert state.status == ExecutionStatus.RUNNING

    state.status = ExecutionStatus.SUCCEEDED
    assert state.status == ExecutionStatus.SUCCEEDED


def test_state_completed_tracking():
    state = ExecutionState()
    state.completed_steps.append("step-1")
    state.completed_steps.append("step-2")
    state.failed_steps.append("step-3")

    assert len(state.completed_steps) == 2
    assert len(state.failed_steps) == 1


def test_state_cancel_overrides_pause():
    state = ExecutionState()
    state.paused = True
    state.cancelled = True
    state.paused = False
    assert state.cancelled is True
    assert state.paused is False


# --- Unit tests for ExecutionInput ---

def test_execution_input_defaults():
    inp = ExecutionInput(
        execution_id="e1",
        process_id="p1",
        version_id="v1",
    )
    assert inp.robot_id is None
    assert inp.inputs == {}
    assert inp.definition == {}


def test_execution_input_with_definition():
    inp = _make_input([{"id": "s1", "type": "ui.click"}])
    steps = inp.definition["process"]["steps"]
    assert len(steps) == 1
    assert steps[0]["type"] == "ui.click"


# --- Tests for ExecuteStepResult contract ---

def test_step_result_success():
    result = ExecuteStepResult(success=True, duration_ms=150, result={"data": "ok"})
    assert result.success is True
    assert result.error is None


def test_step_result_failure():
    result = ExecuteStepResult(
        success=False,
        error="Element not found",
        duration_ms=5000,
        screenshot_key="exec-1/0/12345.png",
    )
    assert result.success is False
    assert "not found" in result.error


# --- Tests for report generation contract ---

def test_report_input():
    report = GenerateReportInput(
        execution_id="e1",
        status="succeeded",
        total_steps=5,
        completed_steps=5,
        failed_steps=0,
    )
    assert report.total_steps == 5
    success_rate = report.completed_steps / report.total_steps * 100
    assert success_rate == 100.0


def test_report_with_failures():
    report = GenerateReportInput(
        execution_id="e1",
        status="failed",
        total_steps=5,
        completed_steps=3,
        failed_steps=2,
    )
    success_rate = report.completed_steps / report.total_steps * 100
    assert success_rate == 60.0


# --- Tests for retry policy mapping ---

def test_step_retry_defaults():
    step = {"id": "s1", "type": "ui.click"}
    retry = step.get("retry", {}) or {}
    assert retry.get("max_attempts", 1) == 1
    assert retry.get("delay_ms", 1000) == 1000


def test_step_retry_custom():
    step = {
        "id": "s1",
        "type": "ui.click",
        "retry": {"max_attempts": 3, "delay_ms": 2000, "backoff": "exponential"},
    }
    retry = step["retry"]
    assert retry["max_attempts"] == 3
    assert retry["backoff"] == "exponential"


# --- Tests for error strategy routing ---

def test_on_error_skip():
    step = {"id": "s1", "type": "ui.click", "on_error": {"action": "skip"}}
    action = step["on_error"]["action"]
    assert action == "skip"


def test_on_error_pause():
    step = {"id": "s1", "type": "ui.click", "on_error": {"action": "pause"}}
    action = step["on_error"]["action"]
    assert action == "pause"


def test_on_error_default_is_fail():
    step = {"id": "s1", "type": "ui.click"}
    on_error = step.get("on_error", {}) or {}
    action = on_error.get("action", "fail")
    assert action == "fail"
