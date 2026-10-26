"""Tests for data transformation pipeline."""

import pytest

from services.data_engine.src.models import TransformOp, TransformType
from services.data_engine.src.transforms import transform


SAMPLE_DATA = [
    {"name": "Alice", "age": 30, "city": "Paris"},
    {"name": "Bob", "age": 25, "city": "Lyon"},
    {"name": "Charlie", "age": 35, "city": "Paris"},
    {"name": "Alice", "age": 30, "city": "Paris"},
]


def test_filter_eq():
    result = transform(SAMPLE_DATA, [
        TransformOp(type=TransformType.FILTER, params={"column": "city", "operator": "eq", "value": "Paris"}),
    ])
    assert result.row_count == 3


def test_filter_gt():
    result = transform(SAMPLE_DATA, [
        TransformOp(type=TransformType.FILTER, params={"column": "age", "operator": "gt", "value": 28}),
    ])
    assert result.row_count == 3


def test_rename():
    result = transform(SAMPLE_DATA, [
        TransformOp(type=TransformType.RENAME, params={"columns": {"name": "full_name"}}),
    ])
    assert "full_name" in result.columns
    assert "name" not in result.columns


def test_drop():
    result = transform(SAMPLE_DATA, [
        TransformOp(type=TransformType.DROP, params={"columns": ["city"]}),
    ])
    assert "city" not in result.columns


def test_sort():
    result = transform(SAMPLE_DATA, [
        TransformOp(type=TransformType.SORT, params={"by": ["age"], "ascending": True}),
    ])
    assert result.data[0]["age"] == 25


def test_deduplicate():
    result = transform(SAMPLE_DATA, [
        TransformOp(type=TransformType.DEDUPLICATE, params={}),
    ])
    assert result.row_count == 3


def test_fill_null():
    data = [{"a": 1, "b": None}, {"a": None, "b": 2}]
    result = transform(data, [
        TransformOp(type=TransformType.FILL_NULL, params={"column": "a", "value": 0}),
    ])
    assert result.data[1]["a"] == 0


def test_chain_filter_sort():
    result = transform(SAMPLE_DATA, [
        TransformOp(type=TransformType.FILTER, params={"column": "city", "operator": "eq", "value": "Paris"}),
        TransformOp(type=TransformType.SORT, params={"by": ["age"]}),
    ])
    assert result.row_count == 3
    assert result.data[0]["age"] == 30
