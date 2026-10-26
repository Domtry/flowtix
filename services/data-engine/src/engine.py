"""Data engine facade — single entry point for data steps in process execution."""

from __future__ import annotations

from typing import Any

import structlog

from .models import (
    DataFormat,
    DataResult,
    ReadRequest,
    TransformOp,
    ValidationRule,
    WriteRequest,
)
from .readers import read_data
from .transforms import transform
from .validator import validate
from .variables import VariableManager
from .writers import write_data

logger = structlog.get_logger()


class DataEngine:
    """Orchestrates read, transform, validate, write operations for process steps."""

    def __init__(self, variables: VariableManager | None = None):
        self.variables = variables or VariableManager()

    def execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        step_type = step.get("type", "")
        params = self.variables.resolve_any(step.get("params", {}))

        handlers = {
            "data.extract": self._extract,
            "data.transform": self._transform,
            "data.validate": self._validate,
            "data.load": self._load,
        }

        handler = handlers.get(step_type)
        if not handler:
            raise ValueError(f"Unknown data step type: {step_type}")

        result = handler(params)

        output_var = params.get("output_variable")
        if output_var and isinstance(result, dict) and "data" in result:
            self.variables.set(output_var, result["data"])

        return result

    def _extract(self, params: dict[str, Any]) -> dict[str, Any]:
        request = ReadRequest(
            source=params["source"],
            format=DataFormat(params["format"]),
            csv_options=params.get("csv_options"),
            excel_options=params.get("excel_options"),
            json_options=params.get("json_options"),
            xml_options=params.get("xml_options"),
        )
        result = read_data(request)
        return result.model_dump()

    def _transform(self, params: dict[str, Any]) -> dict[str, Any]:
        data = params.get("data")
        if isinstance(data, str):
            data = self.variables.get(data)
        if not data:
            raise ValueError("Transform requires data (inline list or variable name)")

        ops = [TransformOp(**op) for op in params.get("operations", [])]
        result = transform(data, ops)
        return result.model_dump()

    def _validate(self, params: dict[str, Any]) -> dict[str, Any]:
        data = params.get("data")
        if isinstance(data, str):
            data = self.variables.get(data)
        if not data:
            raise ValueError("Validate requires data")

        rules = [ValidationRule(**r) for r in params.get("rules", [])]
        result = validate(data, rules)
        return result.model_dump()

    def _load(self, params: dict[str, Any]) -> dict[str, Any]:
        data = params.get("data")
        if isinstance(data, str):
            data = self.variables.get(data)
        if not data:
            raise ValueError("Load requires data")

        request = WriteRequest(
            destination=params["destination"],
            format=DataFormat(params["format"]),
            csv_options=params.get("csv_options"),
            excel_options=params.get("excel_options"),
            json_options=params.get("json_options"),
            xml_options=params.get("xml_options"),
        )
        path = write_data(data, request)
        return {"destination": path, "row_count": len(data)}
