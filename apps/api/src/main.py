from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.database import init_db
from .models.process import *  # noqa: F401,F403 — register SQLModel tables
from .routers import ai, data, executions, health, processes, recording, robots, users, ws


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


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
app.include_router(ws.router)
