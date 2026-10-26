"""Tests for variable manager."""

from services.data_engine.src.variables import VariableManager


def test_set_get():
    vm = VariableManager()
    vm.set("foo", "bar")
    assert vm.get("foo") == "bar"


def test_input_scope():
    vm = VariableManager(inputs={"user": "alice"})
    assert vm.get("user") == "alice"


def test_step_scope_priority():
    vm = VariableManager()
    vm.set("x", "global_val")
    vm.set("x", "step_val", scope="step")
    assert vm.get("x") == "step_val"


def test_clear_step():
    vm = VariableManager()
    vm.set("x", "step_val", scope="step")
    vm.clear_step()
    assert vm.get("x") is None


def test_resolve_simple():
    vm = VariableManager(inputs={"name": "Alice"})
    assert vm.resolve("Hello ${name}!") == "Hello Alice!"


def test_resolve_scoped():
    vm = VariableManager()
    vm.set("count", 42)
    assert vm.resolve("Total: ${global.count}") == "Total: 42"


def test_resolve_missing_kept():
    vm = VariableManager()
    assert vm.resolve("${unknown}") == "${unknown}"


def test_resolve_any_dict():
    vm = VariableManager(inputs={"file": "data.csv"})
    result = vm.resolve_any({"source": "${file}", "count": 10})
    assert result == {"source": "data.csv", "count": 10}


def test_outputs():
    vm = VariableManager()
    vm.set_output("result", [1, 2, 3])
    assert vm.get_outputs() == {"result": [1, 2, 3]}


def test_snapshot():
    vm = VariableManager(inputs={"a": 1})
    vm.set("b", 2)
    snap = vm.snapshot()
    assert snap["input"]["a"] == 1
    assert snap["global"]["b"] == 2
