"""Temporal worker — connects to the Temporal server and runs workflows + activities."""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from .activities import execute_step, generate_report, save_step_result, update_execution_status
from .workflows import ProcessExecutionWorkflow

TASK_QUEUE = "flowtix-execution"
TEMPORAL_ADDRESS = "localhost:7233"


async def run_worker() -> None:
    client = await Client.connect(TEMPORAL_ADDRESS)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ProcessExecutionWorkflow],
        activities=[
            execute_step,
            update_execution_status,
            save_step_result,
            generate_report,
        ],
    )

    print(f"Worker started, listening on task queue: {TASK_QUEUE}")
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
