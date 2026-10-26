"""Tests for data validation engine."""

import pytest

from services.data_engine.src.models import ValidationRule, ValidationType
from services.data_engine.src.validator import validate


SAMPLE_DATA = [
    {"name": "Alice", "age": 30, "email": "alice@test.com"},
    {"name": "Bob", "age": 25, "email": "bob@test.com"},
    {"name": "", "age": -5, "email": "invalid"},
]


def test_not_null_pass():
    result = validate(SAMPLE_DATA[:2], [
        ValidationRule(column="name", type=ValidationType.NOT_NULL),
    ])
    assert result.valid


def test_not_null_fail():
    result = validate(SAMPLE_DATA, [
        ValidationRule(column="name", type=ValidationType.NOT_NULL),
    ])
    assert not result.valid
    assert len(result.errors) == 1
    assert result.errors[0].row == 2


def test_range():
    result = validate(SAMPLE_DATA, [
        ValidationRule(column="age", type=ValidationType.RANGE, params={"min": 0, "max": 120}),
    ])
    assert not result.valid
    assert result.errors[0].column == "age"


def test_regex():
    result = validate(SAMPLE_DATA, [
        ValidationRule(column="email", type=ValidationType.REGEX, params={"pattern": r"^[\w.+-]+@[\w-]+\.[\w.]+$"}),
    ])
    assert not result.valid
    assert result.errors[0].row == 2


def test_in_list():
    result = validate(SAMPLE_DATA[:2], [
        ValidationRule(column="name", type=ValidationType.IN_LIST, params={"values": ["Alice", "Bob", "Charlie"]}),
    ])
    assert result.valid


def test_unique():
    data = [{"id": 1}, {"id": 2}, {"id": 1}]
    result = validate(data, [
        ValidationRule(column="id", type=ValidationType.UNIQUE),
    ])
    assert not result.valid
    assert len(result.errors) == 1
