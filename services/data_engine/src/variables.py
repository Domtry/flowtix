"""Process variable manager — scoped variable storage for execution context."""

from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger()

EXPRESSION_RE = re.compile(r"\$\{(\w+(?:\.\w+)*)}")


class VariableManager:
    """Manages process variables with scope isolation.

    Scopes: 'global' persists across steps, 'step' is cleared between steps,
    'input' holds execution inputs, 'output' collects results.
    """

    def __init__(self, inputs: dict[str, Any] | None = None):
        self._scopes: dict[str, dict[str, Any]] = {
            "global": {},
            "step": {},
            "input": dict(inputs or {}),
            "output": {},
        }

    def set(self, name: str, value: Any, scope: str = "global") -> None:
        if scope not in self._scopes:
            raise ValueError(f"Unknown scope: {scope}")
        self._scopes[scope][name] = value
        logger.debug("var.set", name=name, scope=scope)

    def get(self, name: str, default: Any = None) -> Any:
        for scope in ("step", "global", "input"):
            if name in self._scopes[scope]:
                return self._scopes[scope][name]
        return default

    def resolve(self, template: str) -> str:
        def _replacer(match: re.Match) -> str:
            path = match.group(1)
            parts = path.split(".")
            if len(parts) == 2 and parts[0] in self._scopes:
                val = self._scopes[parts[0]].get(parts[1])
            else:
                val = self.get(parts[0])
            return str(val) if val is not None else match.group(0)

        return EXPRESSION_RE.sub(_replacer, template)

    def resolve_any(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.resolve(value)
        if isinstance(value, dict):
            return {k: self.resolve_any(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve_any(v) for v in value]
        return value

    def clear_step(self) -> None:
        self._scopes["step"] = {}

    def set_output(self, name: str, value: Any) -> None:
        self._scopes["output"][name] = value

    def get_outputs(self) -> dict[str, Any]:
        return dict(self._scopes["output"])

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {scope: dict(data) for scope, data in self._scopes.items()}
