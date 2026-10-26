"""Tests for the DataEngine facade — end-to-end step execution."""

import json
import pytest
from pathlib import Path

from services.data_engine.src.engine import DataEngine
from services.data_engine.src.variables import VariableManager


@pytest.fixture
def csv_file(tmp_path):
    p = tmp_path / "input.csv"
    p.write_text("name,age\nAlice,30\nBob,25\n", encoding="utf-8")
    return str(p)


def test_extract_step(csv_file):
    engine = DataEngine()
    result = engine.execute_step({
        "type": "data.extract",
        "params": {"source": csv_file, "format": "csv"},
    })
    assert result["row_count"] == 2
    assert result["data"][0]["name"] == "Alice"


def test_extract_stores_variable(csv_file):
    vm = VariableManager()
    engine = DataEngine(variables=vm)
    engine.execute_step({
        "type": "data.extract",
        "params": {"source": csv_file, "format": "csv", "output_variable": "my_data"},
    })
    assert vm.get("my_data") is not None
    assert len(vm.get("my_data")) == 2


def test_transform_step():
    engine = DataEngine()
    data = [{"x": 1, "y": "a"}, {"x": 2, "y": "b"}, {"x": 1, "y": "c"}]
    result = engine.execute_step({
        "type": "data.transform",
        "params": {
            "data": data,
            "operations": [
                {"type": "filter", "params": {"column": "x", "operator": "eq", "value": 1}},
            ],
        },
    })
    assert result["row_count"] == 2


def test_validate_step():
    engine = DataEngine()
    result = engine.execute_step({
        "type": "data.validate",
        "params": {
            "data": [{"name": "Alice"}, {"name": ""}],
            "rules": [{"column": "name", "type": "not_null"}],
        },
    })
    assert not result["valid"]


def test_load_csv(tmp_path):
    dest = str(tmp_path / "out.csv")
    engine = DataEngine()
    result = engine.execute_step({
        "type": "data.load",
        "params": {
            "data": [{"a": 1, "b": 2}, {"a": 3, "b": 4}],
            "destination": dest,
            "format": "csv",
        },
    })
    assert result["row_count"] == 2
    assert Path(dest).exists()


def test_load_json(tmp_path):
    dest = str(tmp_path / "out.json")
    engine = DataEngine()
    engine.execute_step({
        "type": "data.load",
        "params": {
            "data": [{"x": 1}],
            "destination": dest,
            "format": "json",
        },
    })
    loaded = json.loads(Path(dest).read_text())
    assert loaded == [{"x": 1}]


def test_variable_resolution_in_extract(csv_file):
    vm = VariableManager(inputs={"file_path": csv_file})
    engine = DataEngine(variables=vm)
    result = engine.execute_step({
        "type": "data.extract",
        "params": {"source": "${file_path}", "format": "csv"},
    })
    assert result["row_count"] == 2


def test_transform_from_variable():
    vm = VariableManager()
    vm.set("my_data", [{"a": 10}, {"a": 20}, {"a": 30}])
    engine = DataEngine(variables=vm)
    result = engine.execute_step({
        "type": "data.transform",
        "params": {
            "data": "my_data",
            "operations": [
                {"type": "filter", "params": {"column": "a", "operator": "gt", "value": 15}},
            ],
        },
    })
    assert result["row_count"] == 2


def test_unknown_step_type():
    engine = DataEngine()
    with pytest.raises(ValueError, match="Unknown data step type"):
        engine.execute_step({"type": "data.unknown", "params": {}})
