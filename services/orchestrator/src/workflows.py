"""Temporal workflow definitions for process execution.

The ProcessExecutionWorkflow orchestrates the full lifecycle of an RPA process:
- Iterates through steps sequentially
- Manages timeouts and retries per step
- Handles pause/resume/cancel signals
- Persists state after each step for durable resumption
"""

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import (
        ExecuteStepInput,
        ExecuteStepResult,
        UpdateExecutionStatusInput,
        execute_step,
        update_execution_status,
        save_step_result,
        generate_report,
        SaveStepResultInput,
        GenerateReportInput,
    )


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


@dataclass
class ExecutionInput:
    execution_id: str
    process_id: str
    version_id: str
    robot_id: str | None = None
    inputs: dict = field(default_factory=dict)
    definition: dict = field(default_factory=dict)


@dataclass
class ExecutionState:
    status: str = ExecutionStatus.CREATED
    current_step_index: int = 0
    completed_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    step_results: dict[str, Any] = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    error: str | None = None
    paused: bool = False
    cancelled: bool = False


@workflow.defn
class ProcessExecutionWorkflow:
    def __init__(self) -> None:
        self._state = ExecutionState()

    @workflow.run
    async def run(self, input: ExecutionInput) -> dict:
        process = input.definition.get("process", input.definition)
        steps = process.get("steps", [])
        execution_id = input.execution_id

        # Mark as running
        self._state.status = ExecutionStatus.RUNNING
        await workflow.execute_activity(
            update_execution_status,
            UpdateExecutionStatusInput(execution_id=execution_id, status=ExecutionStatus.RUNNING),
            start_to_close_timeout=timedelta(seconds=10),
        )

        for i, step in enumerate(steps):
            # Check for cancellation
            if self._state.cancelled:
                self._state.status = ExecutionStatus.CANCELLED
                break

            # Check for pause — wait until resumed
            while self._state.paused:
                self._state.status = ExecutionStatus.PAUSED
                await workflow.execute_activity(
                    update_execution_status,
                    UpdateExecutionStatusInput(execution_id=execution_id, status=ExecutionStatus.PAUSED),
                    start_to_close_timeout=timedelta(seconds=10),
                )
                await workflow.wait_condition(lambda: not self._state.paused or self._state.cancelled)
                if self._state.cancelled:
                    break

            if self._state.cancelled:
                self._state.status = ExecutionStatus.CANCELLED
                break

            self._state.current_step_index = i
            self._state.status = ExecutionStatus.RUNNING
            step_id = step.get("id", f"step-{i}")
            step_timeout = step.get("timeout_ms", 60000) or 60000
            retry_config = step.get("retry", {}) or {}
            max_attempts = retry_config.get("max_attempts", 1)

            # Configure Temporal retry policy from step definition
            retry_policy = RetryPolicy(
                maximum_attempts=max_attempts,
                initial_interval=timedelta(milliseconds=retry_config.get("delay_ms", 1000)),
                backoff_coefficient=2.0 if retry_config.get("backoff") == "exponential" else 1.0,
            )

            try:
                result: ExecuteStepResult = await workflow.execute_activity(
                    execute_step,
                    ExecuteStepInput(
                        execution_id=execution_id,
                        step=step,
                        inputs=input.inputs,
                        step_index=i,
                    ),
                    start_to_close_timeout=timedelta(milliseconds=step_timeout + 5000),
                    retry_policy=retry_policy,
                )

                # Save step result
                await workflow.execute_activity(
                    save_step_result,
                    SaveStepResultInput(
                        execution_id=execution_id,
                        step_id=step_id,
                        step_index=i,
                        success=result.success,
                        result=result.result,
                        error=result.error,
                        duration_ms=result.duration_ms,
                        screenshot_key=result.screenshot_key,
                    ),
                    start_to_close_timeout=timedelta(seconds=10),
                )

                if result.success:
                    self._state.completed_steps.append(step_id)
                    if result.result:
                        self._state.step_results[step_id] = result.result
                else:
                    on_error = step.get("on_error", {}) or {}
                    error_action = on_error.get("action", "fail")

                    if error_action == "skip":
                        self._state.failed_steps.append(step_id)
                        continue
                    elif error_action == "pause":
                        self._state.paused = True
                        self._state.error = result.error
                        continue
                    else:
                        self._state.failed_steps.append(step_id)
                        self._state.status = ExecutionStatus.FAILED
                        self._state.error = result.error
                        break

            except Exception as exc:
                self._state.failed_steps.append(step_id)
                self._state.status = ExecutionStatus.FAILED
                self._state.error = str(exc)

                await workflow.execute_activity(
                    save_step_result,
                    SaveStepResultInput(
                        execution_id=execution_id,
                        step_id=step_id,
                        step_index=i,
                        success=False,
                        error=str(exc),
                    ),
                    start_to_close_timeout=timedelta(seconds=10),
                )
                break

        # Determine final status
        if self._state.status not in (ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
            if not self._state.paused:
                self._state.status = ExecutionStatus.SUCCEEDED

        # Update final status
        await workflow.execute_activity(
            update_execution_status,
            UpdateExecutionStatusInput(
                execution_id=execution_id,
                status=self._state.status,
                outputs=self._state.step_results,
                error=self._state.error,
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Generate report
        await workflow.execute_activity(
            generate_report,
            GenerateReportInput(
                execution_id=execution_id,
                status=self._state.status,
                total_steps=len(steps),
                completed_steps=len(self._state.completed_steps),
                failed_steps=len(self._state.failed_steps),
            ),
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {
            "status": self._state.status,
            "completed": self._state.completed_steps,
            "failed": self._state.failed_steps,
            "outputs": self._state.step_results,
            "error": self._state.error,
        }

    @workflow.signal
    async def pause(self) -> None:
        self._state.paused = True

    @workflow.signal
    async def resume(self) -> None:
        self._state.paused = False

    @workflow.signal
    async def cancel(self) -> None:
        self._state.cancelled = True
        self._state.paused = False

    @workflow.query
    def get_state(self) -> dict:
        return {
            "status": self._state.status,
            "current_step_index": self._state.current_step_index,
            "completed_steps": self._state.completed_steps,
            "failed_steps": self._state.failed_steps,
            "paused": self._state.paused,
            "cancelled": self._state.cancelled,
            "error": self._state.error,
        }
