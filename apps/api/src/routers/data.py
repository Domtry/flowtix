"""Data engine API routes — extract, transform, validate, load."""

from typing import Any

from fastapi import APIRouter

from services.data_engine.src.engine import DataEngine
from services.data_engine.src.models import (
    DataFormat,
    ReadRequest,
    TransformOp,
    ValidationRule,
    WriteRequest,
)
from services.data_engine.src.variables import VariableManager

router = APIRouter(prefix="/data", tags=["data"])


@router.post("/extract")
async def extract_data(source: str, format: str, options: dict[str, Any] | None = None) -> dict:
    engine = DataEngine()
    params: dict[str, Any] = {"source": source, "format": format}
    if options:
        params.update(options)
    return engine._extract(params)


@router.post("/transform")
async def transform_data(data: list[dict[str, Any]], operations: list[dict[str, Any]]) -> dict:
    engine = DataEngine()
    return engine._transform({"data": data, "operations": operations})


@router.post("/validate")
async def validate_data(data: list[dict[str, Any]], rules: list[dict[str, Any]]) -> dict:
    engine = DataEngine()
    return engine._validate({"data": data, "rules": rules})


@router.post("/load")
async def load_data(
    data: list[dict[str, Any]], destination: str, format: str,
    options: dict[str, Any] | None = None,
) -> dict:
    engine = DataEngine()
    params: dict[str, Any] = {"data": data, "destination": destination, "format": format}
    if options:
        params.update(options)
    return engine._load(params)
