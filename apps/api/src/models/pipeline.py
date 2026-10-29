"""Pipelines: run a recorded process once per row of a data source."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, LargeBinary, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Pipeline(SQLModel, table=True):
    __tablename__ = "pipelines"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None)
    # The robot (AppModule code) of the workflow: every process node of the
    # workflow is executed by this robot, on its platform.
    robot_code: str | None = Field(default=None, max_length=100)
    # legacy single-process pipelines; workflows reference processes from their nodes
    process_id: uuid.UUID | None = Field(default=None, foreign_key="processes.id")
    # None = always run the latest version of the process
    version_id: uuid.UUID | None = Field(default=None, foreign_key="process_versions.id")

    # "file": rows come from the uploaded Excel/CSV; "api": rows are posted by the caller
    source_type: str = Field(default="file", max_length=20)
    source_filename: str | None = Field(default=None, max_length=255)
    source_file: bytes | None = Field(default=None, sa_column=Column(LargeBinary, nullable=True))
    source_sheet: str | None = Field(default=None, max_length=255)

    # {step_id: column_name} — which recorded input step receives which column
    mapping: dict = Field(default_factory=dict, sa_column=Column(JSONB, server_default="{}"))

    schedule_cron: str | None = Field(default=None, max_length=100)
    schedule_enabled: bool = Field(default=False)
    last_scheduled_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    # sha256 of the trigger key; the key itself is only shown once
    api_key_hash: str | None = Field(default=None, max_length=128)
    continue_on_error: bool = Field(default=True)

    # Workflow: {"nodes": [...], "edges": [...]} — see services/workflow. The
    # source/mapping/schedule columns above are the pre-workflow format, only
    # read once to convert old pipelines.
    graph: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    # {schedule_node_id: iso minute of its last firing}
    schedule_state: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))

    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )


class PipelineRun(SQLModel, table=True):
    __tablename__ = "pipeline_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    pipeline_id: uuid.UUID = Field(foreign_key="pipelines.id", index=True)
    trigger: str = Field(max_length=20)  # manual | schedule | api | retry
    # queued | running | cancelling | succeeded | partial | failed | cancelled
    status: str = Field(default="queued", max_length=20, index=True)
    total_rows: int = Field(default=0)
    succeeded: int = Field(default=0)
    failed: int = Field(default=0)
    error: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    # where the run starts (a trigger, or a robot node when retrying failures)
    start_node_id: str | None = Field(default=None, max_length=64)
    start_items: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    # {node_id: {status, runs, items_in, items_out: {port: n}, error, sample_in, sample_out}}
    node_results: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))


class PipelineFile(SQLModel, table=True):
    """Data files of a workflow: sources read by 'Lire un fichier', results written by 'Écrire un fichier'."""

    __tablename__ = "pipeline_files"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    pipeline_id: uuid.UUID = Field(foreign_key="pipelines.id", index=True)
    run_id: uuid.UUID | None = Field(default=None, foreign_key="pipeline_runs.id")
    kind: str = Field(default="source", max_length=10)  # source | output
    filename: str = Field(max_length=255)
    content: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )


class PipelineRunItem(SQLModel, table=True):
    __tablename__ = "pipeline_run_items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(foreign_key="pipeline_runs.id", index=True)
    node_id: str | None = Field(default=None, max_length=64)  # the robot node that ran it
    row_index: int
    row_data: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    status: str = Field(default="pending", max_length=20)  # pending | running | succeeded | failed | skipped
    execution_id: uuid.UUID | None = Field(default=None, foreign_key="executions.id")
    error: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
