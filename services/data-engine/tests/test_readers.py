"""Tests for data readers — CSV, JSON, XML."""

import json
import tempfile
from pathlib import Path

import pytest

from services.data_engine.src.models import DataFormat, ReadRequest
from services.data_engine.src.readers import read_data


@pytest.fixture
def csv_file(tmp_path):
    p = tmp_path / "test.csv"
    p.write_text("name,age,city\nAlice,30,Paris\nBob,25,Lyon\n", encoding="utf-8")
    return str(p)


@pytest.fixture
def json_file(tmp_path):
    p = tmp_path / "test.json"
    p.write_text(json.dumps([
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]), encoding="utf-8")
    return str(p)


@pytest.fixture
def xml_file(tmp_path):
    p = tmp_path / "test.xml"
    p.write_text(
        '<?xml version="1.0"?><data>'
        "<row><name>Alice</name><age>30</age></row>"
        "<row><name>Bob</name><age>25</age></row>"
        "</data>",
        encoding="utf-8",
    )
    return str(p)


def test_read_csv(csv_file):
    result = read_data(ReadRequest(source=csv_file, format=DataFormat.CSV))
    assert result.row_count == 2
    assert result.columns == ["name", "age", "city"]
    assert result.data[0]["name"] == "Alice"


def test_read_csv_semicolon(tmp_path):
    p = tmp_path / "semi.csv"
    p.write_text("a;b\n1;2\n3;4\n", encoding="utf-8")
    from services.data_engine.src.models import CsvOptions
    result = read_data(ReadRequest(
        source=str(p), format=DataFormat.CSV,
        csv_options=CsvOptions(delimiter=";"),
    ))
    assert result.row_count == 2
    assert result.data[0]["a"] == 1


def test_read_json(json_file):
    result = read_data(ReadRequest(source=json_file, format=DataFormat.JSON))
    assert result.row_count == 2
    assert result.data[1]["name"] == "Bob"


def test_read_json_path(tmp_path):
    p = tmp_path / "nested.json"
    p.write_text(json.dumps({"result": {"items": [{"x": 1}, {"x": 2}]}}), encoding="utf-8")
    from services.data_engine.src.models import JsonOptions
    result = read_data(ReadRequest(
        source=str(p), format=DataFormat.JSON,
        json_options=JsonOptions(json_path="result.items"),
    ))
    assert result.row_count == 2


def test_read_xml(xml_file):
    result = read_data(ReadRequest(source=xml_file, format=DataFormat.XML))
    assert result.row_count == 2
    assert result.data[0]["name"] == "Alice"
