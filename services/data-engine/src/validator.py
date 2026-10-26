"""Data validation engine — applies rules to tabular data."""

from __future__ import annotations

import re
from typing import Any

import structlog

from .models import (
    ValidationError,
    ValidationResult,
    ValidationRule,
    ValidationType,
)

logger = structlog.get_logger()

_VALIDATORS: dict[ValidationType, Any] = {}


def _register(vtype: ValidationType):
    def decorator(fn):
        _VALIDATORS[vtype] = fn
        return fn
    return decorator


def validate(data: list[dict[str, Any]], rules: list[ValidationRule]) -> ValidationResult:
    errors: list[ValidationError] = []
    for rule in rules:
        checker = _VALIDATORS.get(rule.type)
        if not checker:
            raise ValueError(f"Unknown validation type: {rule.type}")
        for i, row in enumerate(data):
            value = row.get(rule.column)
            error = checker(i, rule, value)
            if error:
                errors.append(error)

    result = ValidationResult(valid=len(errors) == 0, errors=errors, row_count=len(data))
    logger.info("data.validate", rules=len(rules), rows=len(data), errors=len(errors))
    return result


def _make_error(row: int, rule: ValidationRule, value: Any, default_msg: str) -> ValidationError:
    return ValidationError(
        row=row,
        column=rule.column,
        rule=rule.type,
        message=rule.message or default_msg,
        value=value,
    )


@_register(ValidationType.NOT_NULL)
def _check_not_null(row: int, rule: ValidationRule, value: Any) -> ValidationError | None:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return _make_error(row, rule, value, f"{rule.column} must not be null")
    return None


@_register(ValidationType.UNIQUE)
def _check_unique(row: int, rule: ValidationRule, value: Any) -> ValidationError | None:
    seen = rule.params.setdefault("_seen", set())
    if value in seen:
        return _make_error(row, rule, value, f"{rule.column} must be unique")
    seen.add(value)
    return None


@_register(ValidationType.REGEX)
def _check_regex(row: int, rule: ValidationRule, value: Any) -> ValidationError | None:
    pattern = rule.params.get("pattern", "")
    if value is not None and not re.match(pattern, str(value)):
        return _make_error(row, rule, value, f"{rule.column} must match {pattern}")
    return None


@_register(ValidationType.RANGE)
def _check_range(row: int, rule: ValidationRule, value: Any) -> ValidationError | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return _make_error(row, rule, value, f"{rule.column} must be numeric")
    min_val = rule.params.get("min")
    max_val = rule.params.get("max")
    if min_val is not None and num < float(min_val):
        return _make_error(row, rule, value, f"{rule.column} must be >= {min_val}")
    if max_val is not None and num > float(max_val):
        return _make_error(row, rule, value, f"{rule.column} must be <= {max_val}")
    return None


@_register(ValidationType.IN_LIST)
def _check_in_list(row: int, rule: ValidationRule, value: Any) -> ValidationError | None:
    allowed = rule.params.get("values", [])
    if value is not None and value not in allowed:
        return _make_error(row, rule, value, f"{rule.column} must be one of {allowed}")
    return None


@_register(ValidationType.TYPE_CHECK)
def _check_type(row: int, rule: ValidationRule, value: Any) -> ValidationError | None:
    expected = rule.params.get("dtype", "str")
    if value is None:
        return None
    try:
        {"int": int, "float": float, "str": str, "bool": bool}[expected](value)
    except (KeyError, TypeError, ValueError):
        return _make_error(row, rule, value, f"{rule.column} must be {expected}")
    return None
