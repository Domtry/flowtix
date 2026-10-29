import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


class Process(SQLModel, table=True):
    __tablename__ = "processes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None)
    robot_code: str | None = Field(default=None, max_length=100)
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    versions: list["ProcessVersion"] = Relationship(back_populates="process")


class ProcessVersion(SQLModel, table=True):
    __tablename__ = "process_versions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    process_id: uuid.UUID = Field(foreign_key="processes.id")
    version: int
    schema_version: str = Field(default="1.0", max_length=10)
    definition: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    status: str = Field(default="draft", max_length=20)
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    process: Process | None = Relationship(back_populates="versions")


class Robot(SQLModel, table=True):
    __tablename__ = "robots"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    machine_id: str | None = Field(default=None, max_length=255)
    capabilities: dict = Field(default_factory=dict, sa_column=Column(JSONB, server_default="[]"))
    status: str = Field(default="offline", max_length=20)
    last_heartbeat: datetime | None = Field(default=None)
    registered_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )


class Execution(SQLModel, table=True):
    __tablename__ = "executions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    process_id: uuid.UUID = Field(foreign_key="processes.id")
    version_id: uuid.UUID = Field(foreign_key="process_versions.id")
    robot_id: uuid.UUID | None = Field(default=None, foreign_key="robots.id")
    status: str = Field(default="created", max_length=20)
    current_step_id: str | None = Field(default=None, max_length=255)
    inputs: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    outputs: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    error: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    steps: list["ExecutionStep"] = Relationship(back_populates="execution")


class ExecutionStep(SQLModel, table=True):
    __tablename__ = "execution_steps"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    execution_id: uuid.UUID = Field(foreign_key="executions.id")
    step_id: str = Field(max_length=255)
    step_index: int
    status: str = Field(default="pending", max_length=20)
    attempt: int = Field(default=1)
    result: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    error: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    screenshot_key: str | None = Field(default=None, max_length=512)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)

    execution: Execution | None = Relationship(back_populates="steps")


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)
    name: str = Field(max_length=255)
    password_hash: str = Field(max_length=255)
    role: str = Field(default="operator", max_length=20)
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(max_length=255, unique=True, index=True)
    value: str = Field(default="")


class AppModule(SQLModel, table=True):
    __tablename__ = "app_modules"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=100, unique=True, index=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None)
    action_type: str = Field(default="web", max_length=20)
    engine: str = Field(default="auto", max_length=20)
    executable_path: str = Field(default="", max_length=1024)
    default_url: str | None = Field(default=None, max_length=1024)
    window_title_pattern: str | None = Field(default=None, max_length=255)
    config: dict = Field(default_factory=dict, sa_column=Column(JSONB, server_default="{}"))
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
