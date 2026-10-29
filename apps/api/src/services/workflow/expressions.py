"""Templates and conditions for workflow nodes — no eval: a fixed set of operators.

Templates: "Bonjour {{Nom}}" — a field of the current item; dotted paths reach into
nested values ({{reponse.client.id}}). A field whose name itself contains a dot
("N°.Police") is matched first as a whole.
"""

import re
from typing import Any

_TEMPLATE = re.compile(r"\{\{\s*(.+?)\s*\}\}")
MAX_REGEX_LEN = 500


def get_path(item: Any, path: str) -> Any:
    if isinstance(item, dict) and path in item:
        return item[path]
    current = item
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def _text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (dict, list)):
        import json
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def render(template: Any, item: dict, extra: dict | None = None) -> str:
    """Replace {{field}} by the item's value; unknown fields render empty."""
    if template is None:
        return ""
    scope = {**(extra or {}), **(item or {})}
    return _TEMPLATE.sub(lambda m: _text(get_path(scope, m.group(1))), str(template))


def template_fields(template: str) -> list[str]:
    return [m.group(1) for m in _TEMPLATE.finditer(template or "")]


def _number(v: Any) -> float | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = _text(v).strip().replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _norm(v: Any) -> str:
    return _text(v).strip().lower()


def _compare(a: Any, b: Any) -> int | None:
    x, y = _number(a), _number(b)
    if x is None or y is None:
        return None
    return (x > y) - (x < y)


OPERATORS: dict[str, str] = {
    "equals": "est égal à",
    "not_equals": "est différent de",
    "contains": "contient",
    "not_contains": "ne contient pas",
    "starts_with": "commence par",
    "ends_with": "se termine par",
    "empty": "est vide",
    "not_empty": "n'est pas vide",
    "gt": "est supérieur à",
    "gte": "est supérieur ou égal à",
    "lt": "est inférieur à",
    "lte": "est inférieur ou égal à",
    "regex": "correspond à l'expression régulière",
}
UNARY = {"empty", "not_empty"}


def evaluate(rule: dict, item: dict) -> bool:
    """One rule: {"field": "Montant", "op": "gt", "value": "1000"}.
    Text comparisons ignore case and surrounding spaces; numeric ones accept 1 000,50."""
    op = rule.get("op", "equals")
    actual = get_path(item, rule.get("field", ""))
    expected = render(rule.get("value", ""), item)
    if op == "empty":
        return _norm(actual) == ""
    if op == "not_empty":
        return _norm(actual) != ""
    if op in ("gt", "gte", "lt", "lte"):
        c = _compare(actual, expected)
        if c is None:
            return False
        return {"gt": c > 0, "gte": c >= 0, "lt": c < 0, "lte": c <= 0}[op]
    a, e = _norm(actual), _norm(expected)
    if op == "equals":
        c = _compare(actual, expected)
        return c == 0 if c is not None else a == e
    if op == "not_equals":
        c = _compare(actual, expected)
        return c != 0 if c is not None else a != e
    if op == "contains":
        return e in a
    if op == "not_contains":
        return e not in a
    if op == "starts_with":
        return a.startswith(e)
    if op == "ends_with":
        return a.endswith(e)
    if op == "regex":
        pattern = render(rule.get("value", ""), item)
        if len(pattern) > MAX_REGEX_LEN:
            raise ValueError("Expression régulière trop longue")
        return re.search(pattern, _text(actual), re.IGNORECASE) is not None
    raise ValueError(f"Opérateur inconnu : {op}")


def matches(config: dict, item: dict) -> bool:
    rules = config.get("rules") or []
    if not rules:
        return True
    results = (evaluate(r, item) for r in rules)
    return any(results) if config.get("combine") == "or" else all(results)
