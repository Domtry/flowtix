import io
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from src.services import cron
from src.services.pipeline_source import SourceError, parse_source
from src.services.workflow import nodes as wf_nodes
from src.services.workflow.catalog import validate
from src.services.workflow.engine import WorkflowEngine, WorkflowFailed
from src.services.workflow.expressions import evaluate, matches, render
from src.services.workflow.legacy import build_legacy_graph

# ------------------------------------------------------------------ sources


def test_excel_values_are_typed_like_a_user_would():
    buf = io.BytesIO()
    pd.DataFrame({
        "Nom": ["KOUASSI", None],
        "Montant": [30000, None],
        "Date": [datetime(2026, 1, 5), None],
        "Code": ["00873", None],
    }).to_excel(buf, index=False)
    columns, rows = parse_source("a.xlsx", buf.getvalue())
    assert columns == ["Nom", "Montant", "Date", "Code"]
    assert rows == [{"Nom": "KOUASSI", "Montant": "30000", "Date": "05/01/2026", "Code": "00873"}]


def test_csv_semicolon_cp1252_keeps_leading_zeros():
    content = "Nom;Prénom;N°.Police\nKOUASSI;Boris;0042\n".encode("cp1252")
    columns, rows = parse_source("b.csv", content)
    assert columns == ["Nom", "Prénom", "N°.Police"]
    assert rows == [{"Nom": "KOUASSI", "Prénom": "Boris", "N°.Police": "0042"}]


@pytest.mark.parametrize("name,content", [("c.csv", b"a,a\n1,2\n"), ("d.pdf", b"x")])
def test_invalid_sources_are_rejected(name, content):
    with pytest.raises(SourceError):
        parse_source(name, content)


# --------------------------------------------------------------------- cron


def test_cron_matching():
    wednesday_8am = datetime(2026, 10, 28, 8, 0)
    assert cron.matches("0 8 * * 1-5", wednesday_8am)
    assert not cron.matches("0 8 * * 0,6", wednesday_8am)
    assert cron.matches("*/15 * * * *", wednesday_8am.replace(minute=45))
    assert not cron.matches("0 9 * * *", wednesday_8am)


def test_cron_next_run():
    t = datetime(2026, 10, 28, 8, 0)
    assert cron.next_run("30 7 * * 1", t) == datetime(2026, 11, 2, 7, 30)
    assert cron.next_run("0 0 1 1 *", t) == datetime(2027, 1, 1, 0, 0)


@pytest.mark.parametrize("expr", ["* * *", "61 * * * *", "a * * * *", "*/0 * * * *"])
def test_cron_rejects_invalid(expr):
    with pytest.raises(ValueError):
        cron.parse(expr)


# -------------------------------------------------------------- expressions


def test_render_templates():
    item = {"Nom": "KOUASSI", "N°.Police": "0042", "rep": {"client": {"id": 7}}, "x": 30000.0}
    assert render("{{Nom}}-{{N°.Police}}", item) == "KOUASSI-0042"
    assert render("id={{ rep.client.id }} m={{x}} z={{absent}}", item) == "id=7 m=30000 z="


@pytest.mark.parametrize("rule,expected", [
    ({"field": "Montant", "op": "gt", "value": "1000"}, True),
    ({"field": "Montant", "op": "lte", "value": "1 000,50"}, False),
    ({"field": "Nom", "op": "equals", "value": " kouassi "}, True),
    ({"field": "Nom", "op": "contains", "value": "UAS"}, True),
    ({"field": "Vide", "op": "empty"}, True),
    ({"field": "Code", "op": "equals", "value": "42"}, True),
    ({"field": "Code", "op": "regex", "value": r"^00\d+$"}, True),
    ({"field": "Nom", "op": "equals", "value": "{{Copie}}"}, True),
])
def test_conditions(rule, expected):
    item = {"Montant": "30 000", "Nom": "KOUASSI", "Vide": "", "Code": "0042", "Copie": "Kouassi"}
    assert evaluate(rule, item) is expected


def test_combined_rules():
    item = {"a": "1", "b": "2"}
    rules = [{"field": "a", "op": "equals", "value": "1"}, {"field": "b", "op": "equals", "value": "3"}]
    assert not matches({"rules": rules}, item)
    assert matches({"rules": rules, "combine": "or"}, item)


def test_set_fields_operations():
    cfg = {"operations": [
        {"op": "set", "field": "Complet", "value": "{{Prenom}} {{Nom}}", "case": "upper"},
        {"op": "rename", "field": "Nom", "to": "Famille"},
        {"op": "remove", "field": "Prenom"},
    ]}
    assert wf_nodes.set_fields(cfg, {"Nom": "Yao", "Prenom": "Marc"}) == {"Complet": "MARC YAO", "Famille": "Yao"}
    assert wf_nodes.set_fields({"keep_only": "Nom, X"}, {"Nom": "A", "B": 1}) == {"Nom": "A", "X": ""}


# --------------------------------------------------------------- validation


def _n(nid, type_, config=None):
    return {"id": nid, "type": type_, "name": nid, "position": {"x": 0, "y": 0}, "config": config or {}}


def _e(src, tgt, sp="main", tp="main"):
    return {"id": f"{src}-{tgt}-{sp}", "source": src, "source_port": sp, "target": tgt, "target_port": tp}


def test_validation_requires_trigger_and_config():
    issues = validate({"nodes": [_n("r", "robot.run")], "edges": []})
    messages = " ".join(i["message"] for i in issues)
    assert "point de démarrage" in messages and "point de clôture" in messages and "processus" in messages


def test_validation_cycle_only_through_loop():
    w = {"cron": "0 8 * * *"}
    ok = {"nodes": [_n("t", "trigger.schedule", w), _n("l", "logic.loop"), _n("s", "data.set"),
                    _n("fin", "flow.end")],
          "edges": [_e("t", "l"), _e("l", "s", "item"), _e("s", "l"), _e("l", "fin", "done")]}
    assert validate(ok) == []
    bad = {"nodes": [_n("t", "trigger.manual"), _n("a", "data.set"), _n("b", "data.set")],
           "edges": [_e("t", "a"), _e("a", "b"), _e("b", "a")]}
    assert any("Boucle infinie" in i["message"] for i in validate(bad))


# ------------------------------------------------------------------- engine


class FakeCtx:
    def __init__(self):
        self.results = {}
        self.calls = []

    async def check_cancel(self):
        pass

    async def record(self, node_id, items_in, outputs, error, duration_ms):
        r = self.results.setdefault(node_id, {"runs": 0, "out": {}, "error": None})
        r["runs"] += 1
        for port, items in outputs.items():
            r["out"].setdefault(port, []).extend(items)
        r["error"] = error


def _collector(name, ctx_log):
    async def ex(node, items, ctx):
        ctx_log.append((name, [dict(i) for i in items]))
        return {"main": items}
    return ex


async def _run(graph, items, extra=None):
    ctx = FakeCtx()
    log: list = []
    executors = dict(wf_nodes.EXECUTORS)
    executors["data.write_file"] = _collector("sink", log)
    executors.update(extra or {})
    await WorkflowEngine(graph, executors, ctx).run("t", items)
    return ctx, log


async def test_if_routes_items():
    g = {"nodes": [_n("t", "trigger.manual"),
                   _n("if", "logic.if", {"rules": [{"field": "m", "op": "gt", "value": "10"}]}),
                   _n("big", "data.set", {"operations": [{"op": "set", "field": "k", "value": "gros"}]}),
                   _n("small", "data.set", {"operations": [{"op": "set", "field": "k", "value": "petit"}]}),
                   _n("sink", "data.write_file")],
         "edges": [_e("t", "if"), _e("if", "big", "true"), _e("if", "small", "false"),
                   _e("big", "sink"), _e("small", "sink")]}
    ctx, log = await _run(g, [{"m": "5"}, {"m": "50"}, {"m": "7"}])
    assert ctx.results["if"]["out"] == {"true": [{"m": "50"}], "false": [{"m": "5"}, {"m": "7"}]}
    got = sorted(i["k"] for _, batch in log for i in batch)
    assert got == ["gros", "petit", "petit"]


async def test_loop_with_return_collects_results_in_batches():
    g = {"nodes": [_n("t", "trigger.manual"), _n("l", "logic.loop", {"batch_size": 2}),
                   _n("body", "data.set", {"operations": [{"op": "set", "field": "vu", "value": "oui"}]}),
                   _n("sink", "data.write_file")],
         "edges": [_e("t", "l"), _e("l", "body", "item"), _e("body", "l"), _e("l", "sink", "done")]}
    ctx, log = await _run(g, [{"i": n} for n in range(5)])
    assert ctx.results["body"]["runs"] == 3  # batches of 2, 2, 1
    assert log == [("sink", [{"i": n, "vu": "oui"} for n in range(5)])]


async def test_loop_dead_end_body_still_iterates():
    seen = []

    async def body(node, items, ctx):
        seen.append([i["i"] for i in items])
        return {"main": items}

    g = {"nodes": [_n("t", "trigger.manual"), _n("l", "logic.loop"), _n("b", "logic.wait"),
                   _n("sink", "data.write_file")],
         "edges": [_e("t", "l"), _e("l", "b", "item"), _e("l", "sink", "done")]}
    ctx, log = await _run(g, [{"i": 1}, {"i": 2}, {"i": 3}], {"logic.wait": body})
    assert seen == [[1], [2], [3]]  # one at a time, in order
    assert log == [("sink", [{"i": 1}, {"i": 2}, {"i": 3}])]


async def test_nested_loops():
    order = []

    async def inner_body(node, items, ctx):
        order.append(items[0]["v"])
        return {"main": items}

    async def explode(node, items, ctx):
        return {"main": [{"v": f"{items[0]['o']}{c}"} for c in "ab"]}

    g = {"nodes": [_n("t", "trigger.manual"), _n("outer", "logic.loop"), _n("x", "data.set"),
                   _n("inner", "logic.loop"), _n("w", "logic.wait")],
         "edges": [_e("t", "outer"), _e("outer", "x", "item"), _e("x", "inner"),
                   _e("inner", "w", "item"), _e("w", "inner"), _e("inner", "outer", "done")]}
    await _run(g, [{"o": 1}, {"o": 2}], {"data.set": explode, "logic.wait": inner_body})
    assert order == ["1a", "1b", "2a", "2b"]


async def test_merge_waits_for_both_branches():
    g = {"nodes": [_n("t", "trigger.manual"),
                   _n("if", "logic.if", {"rules": [{"field": "k", "op": "equals", "value": "a"}]}),
                   _n("m", "logic.merge"), _n("sink", "data.write_file")],
         "edges": [_e("t", "if"), _e("if", "m", "true", "a"), _e("if", "m", "false", "b"), _e("m", "sink")]}
    ctx, log = await _run(g, [{"k": "b"}, {"k": "a"}])
    assert log == [("sink", [{"k": "a"}, {"k": "b"}])]


async def test_node_error_stops_run_and_is_recorded():
    async def boom(node, items, ctx):
        raise ValueError("fichier absent")

    g = {"nodes": [_n("t", "trigger.manual"), _n("r", "data.read_file"), _n("sink", "data.write_file")],
         "edges": [_e("t", "r"), _e("r", "sink")]}
    with pytest.raises(WorkflowFailed) as exc:
        await _run(g, [{}], {"data.read_file": boom})
    assert exc.value.node_id == "r" and "fichier absent" in exc.value.message


async def test_robot_node_splits_success_and_error():
    class RobotCtx(FakeCtx):
        async def run_robot(self, node, process_id, version_id, values, item, session=None):
            return (item["ok"] == "1", None if item["ok"] == "1" else "Element introuvable", "exec-1")

    node = _n("r", "robot.run", {"process_id": "p", "mapping": {"s1": "{{Login}}"}})
    out = await wf_nodes.robot_run(node, [{"ok": "1", "Login": "a"}, {"ok": "0", "Login": "b"}], RobotCtx())
    assert [i["Login"] for i in out["success"]] == ["a"]
    assert out["error"][0]["_erreur"] == "Element introuvable"


# ------------------------------------------------------------------- legacy


def test_legacy_pipeline_becomes_trigger_reader_robot():
    p = SimpleNamespace(schedule_cron="0 8 * * 1-5", schedule_enabled=True, source_type="file",
                        api_key_hash="h", process_id="proc", version_id=None,
                        mapping={"s1": "Login"}, source_sheet=None)
    g = build_legacy_graph(p, "file-1")
    types = [n["type"] for n in g["nodes"]]
    assert types.count("trigger.manual") == 1 and "trigger.schedule" in types and "trigger.webhook" in types
    robot = next(n for n in g["nodes"] if n["type"] == "robot.run")
    assert robot["config"]["mapping"] == {"s1": "{{Login}}"}
    assert validate(g, "SANLAM_PORTAL") == []


# ------------------------------------------------------------ keep session


def _proc(*types):
    return {"process": {"steps": [{"id": f"s{i}", "type": t, "metadata": {"path_from_prev": [[1, 2, 3]]}}
                                  for i, t in enumerate(types)]}}


def test_keep_session_skips_launch_steps_by_default():
    d = _proc("browser.navigate", "browser.wait", "ui.click", "ui.fill")
    out = wf_nodes.keep_session(d, None)["process"]["steps"]
    assert [s["id"] for s in out] == ["s2", "s3"]
    assert "path_from_prev" not in out[0]["metadata"]  # no previous click to anchor the path on
    assert len(d["process"]["steps"]) == 4  # original untouched


def test_keep_session_resumes_at_chosen_step():
    d = _proc("browser.navigate", "ui.click", "ui.fill", "ui.click", "ui.fill")
    assert [s["id"] for s in wf_nodes.keep_session(d, "s3")["process"]["steps"]] == ["s3", "s4"]
    with pytest.raises(wf_nodes.NodeError):
        wf_nodes.keep_session(d, "absent")


async def test_robot_node_passes_session_option():
    seen = {}

    class Ctx(FakeCtx):
        async def run_robot(self, node, process_id, version_id, values, item, session=None):
            seen.update(session)
            return True, None, "e"

    node = _n("r", "robot.run", {"process_id": "p", "keep_session": True, "start_step_id": "s5"})
    await wf_nodes.robot_run(node, [{}], Ctx())
    assert seen == {"keep": True, "start_step_id": "s5"}


# ------------------------------------------------------- workflow robot / switch


def test_process_nodes_need_the_workflow_robot():
    g = {"nodes": [_n("t", "trigger.manual"), _n("p", "robot.run", {"process_id": "proc-orass"}),
                   _n("fin", "flow.end")],
         "edges": [_e("t", "p"), _e("p", "fin", "success")]}
    assert any("robot du workflow" in i["message"] for i in validate(g))
    robots = {"proc-orass": "ORASS", "proc-portal": "SANLAM_PORTAL"}
    assert validate(g, "ORASS", robots) == []
    wrong = validate(g, "SANLAM_PORTAL", robots)
    assert wrong and wrong[0]["node_id"] == "p" and "appartient au robot ORASS" in wrong[0]["message"]


def _switch(cases, op="equals"):
    return _n("sw", "logic.switch", {"field": "Option", "op": op, "cases": cases})


async def test_switch_routes_each_option_to_its_process():
    cases = [{"id": "ess", "value": "Essentiel"}, {"id": "conf", "value": "Confort"}]
    out = await wf_nodes.logic_switch(_switch(cases), [
        {"Option": "essentiel"}, {"Option": "Confort"}, {"Option": "Premium"}, {"Option": " CONFORT "},
    ], None)
    assert [i["Option"] for i in out["ess"]] == ["essentiel"]
    assert [i["Option"] for i in out["conf"]] == ["Confort", " CONFORT "]
    assert [i["Option"] for i in out["default"]] == ["Premium"]


def test_switch_edges_use_case_outputs():
    cases = [{"id": "ess", "value": "Essentiel"}]
    g = {"nodes": [_n("t", "trigger.manual"), _switch(cases), _n("a", "data.set"), _n("b", "data.set"),
                   _n("fin", "flow.end")],
         "edges": [_e("t", "sw"), _e("sw", "a", "ess"), _e("sw", "b", "default"), _e("a", "fin"), _e("b", "fin")]}
    assert validate(g) == []
    g["edges"].append(_e("sw", "b", "supprime"))
    assert any("Sortie inconnue" in i["message"] for i in validate(g))


# --------------------------------------------------------- start & closing points


def test_final_status_from_closing_points():
    from src.services.pipeline_runner import final_status
    ok = {"name": "Fin", "result": "success", "count": 3, "message": ""}
    ko = {"name": "Fin refus", "result": "failure", "count": 1, "message": "Option inconnue : Gold"}
    assert final_status([ok], 0) == ("succeeded", None)
    assert final_status([ok], 2) == ("partial", None)
    assert final_status([ok, ko], 0) == ("partial", "Fin refus (1) : Option inconnue : Gold")
    assert final_status([ko], 0)[0] == "failed"


async def test_end_node_records_rendered_message():
    class Ctx(FakeCtx):
        ends: list = []
    ctx = Ctx()
    ctx.ends = []
    node = _n("fin", "flow.end", {"result": "failure", "message": "{{nombre}} contrat(s) refusé(s), ex. {{Nom}}"})
    assert await wf_nodes.flow_end(node, [{"Nom": "YAO"}, {"Nom": "KONAN"}], ctx) == {}
    assert ctx.ends[0]["message"] == "2 contrat(s) refusé(s), ex. YAO"


def test_missing_closing_point_is_added_to_dangling_branches():
    from src.services.workflow.legacy import with_end_node
    cases = [{"id": "ess", "value": "Essentiel"}]
    g = {"nodes": [_n("t", "trigger.manual"), _switch(cases), _n("a", "data.set"), _n("b", "data.set")],
         "edges": [_e("t", "sw"), _e("sw", "a", "ess"), _e("sw", "b", "default")]}
    out = with_end_node(g)
    end = next(n for n in out["nodes"] if n["type"] == "flow.end")
    assert sorted(e["source"] for e in out["edges"] if e["target"] == end["id"]) == ["a", "b"]
    assert validate(out) == []
