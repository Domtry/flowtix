"""AI engine API routes — Ollama tasks, model management."""

from fastapi import APIRouter

from services.ai.src.models import AiRequest
from services.ai.src.service import AiService

router = APIRouter(prefix="/ai", tags=["ai"])

_service = AiService()


@router.get("/health")
async def ai_health():
    ok = await _service.health()
    return {"status": "ok" if ok else "unavailable"}


@router.get("/models")
async def list_models():
    models = await _service.list_models()
    return [m.model_dump() for m in models]


@router.post("/execute")
async def execute_task(request: AiRequest):
    response = await _service.execute(request)
    return response.model_dump()


@router.post("/classify")
async def classify(data: str, categories: list[str]):
    response = await _service.classify(data, categories)
    return response.model_dump()


@router.post("/extract")
async def extract(data: str, fields: list[str]):
    response = await _service.extract(data, fields)
    return response.model_dump()


@router.post("/repair-selector")
async def repair_selector(selector: str, html: str):
    response = await _service.repair_selector(selector, html)
    return response.model_dump()
