"""Execution service — bridges the API with Temporal for process execution."""

from datetime import datetime, timezone
from uuid import UUID

from temporalio.client import Client

from services.orchestrator.src.workflows import ExecutionInput, ProcessExecutionWorkflow

TASK_QUEUE = "flowtix-execution"


class ExecutionService:
    def __init__(self, temporal_address: str = "localhost:7233") -> None:
        self._address = temporal_address
        self._client: Client | None = None

    async def _get_client(self) -> Client:
        if not self._client:
            self._client = await Client.connect(self._address)
        return self._client

    async def start_execution(
        self,
        execution_id: str,
        process_id: str,
        version_id: str,
        definition: dict,
        inputs: dict | None = None,
        robot_id: str | None = None,
    ) -> str:
        """Start a Temporal workflow for the given execution."""
        client = await self._get_client()
        workflow_id = f"execution-{execution_id}"

        handle = await client.start_workflow(
            ProcessExecutionWorkflow.run,
            ExecutionInput(
                execution_id=execution_id,
                process_id=process_id,
                version_id=version_id,
                robot_id=robot_id,
                inputs=inputs or {},
                definition=definition,
            ),
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        return workflow_id

    async def pause_execution(self, execution_id: str) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(f"execution-{execution_id}")
        await handle.signal(ProcessExecutionWorkflow.pause)

    async def resume_execution(self, execution_id: str) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(f"execution-{execution_id}")
        await handle.signal(ProcessExecutionWorkflow.resume)

    async def cancel_execution(self, execution_id: str) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(f"execution-{execution_id}")
        await handle.signal(ProcessExecutionWorkflow.cancel)

    async def get_execution_state(self, execution_id: str) -> dict:
        client = await self._get_client()
        handle = client.get_workflow_handle(f"execution-{execution_id}")
        return await handle.query(ProcessExecutionWorkflow.get_state)

    async def wait_for_result(self, execution_id: str) -> dict:
        client = await self._get_client()
        handle = client.get_workflow_handle(f"execution-{execution_id}")
        return await handle.result()
