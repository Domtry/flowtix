from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.database import init_db
from .models.process import *  # noqa: F401,F403 — register SQLModel tables
from .models.pipeline import *  # noqa: F401,F403
from .routers import (
    ai, app_modules, data, executions, health, integrations, pipelines, processes, recording, robots,
    users, ws,
)
from .routers import settings as settings_router
from .core.database import async_session
from .services.pipeline_runner import runner as pipeline_runner
from .services.workflow.legacy import convert_legacy_pipelines


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    async with async_session() as db:
        await convert_legacy_pipelines(db)
    pipeline_runner.start()
    yield
    await pipeline_runner.stop()


app = FastAPI(
    title="FlowtTix API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(processes.router, prefix="/api/v1")
app.include_router(recording.router, prefix="/api/v1")
app.include_router(executions.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(robots.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(app_modules.router, prefix="/api/v1")
app.include_router(pipelines.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(ws.router)
