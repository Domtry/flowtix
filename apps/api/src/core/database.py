from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from .config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_async_engine(settings.database_url, echo=False, connect_args=connect_args)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# create_all never alters existing tables: columns added after a table was first
# created are declared here (idempotent).
_ADDED_COLUMNS = [
    ("pipelines", "graph", "JSONB"),
    ("pipelines", "robot_code", "VARCHAR(100)"),
    ("pipelines", "schedule_state", "JSONB"),
    ("pipeline_runs", "node_results", "JSONB"),
    ("pipeline_runs", "start_node_id", "VARCHAR(64)"),
    ("pipeline_runs", "start_items", "JSONB"),
    ("pipeline_run_items", "node_id", "VARCHAR(64)"),
]


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        if engine.dialect.name == "postgresql":
            for table, column, sql_type in _ADDED_COLUMNS:
                await conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {sql_type}"
                )
            await conn.exec_driver_sql("ALTER TABLE pipelines ALTER COLUMN process_id DROP NOT NULL")


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session() as session:
        yield session
