"""Minimal 5-field cron matcher (minute hour day-of-month month day-of-week).

Supports *, numbers, ranges a-b, steps */n and a-b/n, and comma lists.
Day-of-week: 0 or 7 = Sunday. Times are evaluated in the server timezone (UTC,
which is local time in Côte d'Ivoire).
"""

from datetime import datetime, timedelta

_BOUNDS = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
_NAMES = ["minute", "heure", "jour du mois", "mois", "jour de la semaine"]


def _parse_field(field: str, lo: int, hi: int, name: str) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            if not step_s.isdigit() or int(step_s) == 0:
                raise ValueError(f"Pas invalide pour {name} : {step_s}")
            step = int(step_s)
        if part == "*":
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            if not (a.isdigit() and b.isdigit()):
                raise ValueError(f"Intervalle invalide pour {name} : {part}")
            start, end = int(a), int(b)
        elif part.isdigit():
            start = end = int(part)
        else:
            raise ValueError(f"Valeur invalide pour {name} : {part}")
        if start < lo or end > hi or start > end:
            raise ValueError(f"{name} hors limites ({lo}-{hi}) : {part}")
        values.update(range(start, end + 1, step))
    return values


def parse(expr: str) -> list[set[int]]:
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError("Une expression cron a 5 champs : minute heure jour mois jour-semaine")
    parsed = [_parse_field(f, lo, hi, n) for f, (lo, hi), n in zip(fields, _BOUNDS, _NAMES)]
    if 7 in parsed[4]:
        parsed[4].add(0)
    return parsed


def _day_ok(parsed: list[set[int]], dt: datetime) -> bool:
    _, _, dom, _, dow = parsed
    cron_dow = (dt.weekday() + 1) % 7  # Python: Monday=0 ; cron: Sunday=0
    # Standard cron: when both day fields are restricted, either may match.
    if len(dom) < 31 and len(dow) < 8:
        return (dt.day in dom) or (cron_dow in dow)
    return (dt.day in dom) and (cron_dow in dow)


def _match_parsed(parsed: list[set[int]], dt: datetime) -> bool:
    minute, hour, _, month, _ = parsed
    return dt.minute in minute and dt.hour in hour and dt.month in month and _day_ok(parsed, dt)


def matches(expr: str, dt: datetime) -> bool:
    return _match_parsed(parse(expr), dt)


def next_run(expr: str, after: datetime, horizon_days: int = 400) -> datetime | None:
    """First matching minute strictly after `after`, or None within the horizon."""
    parsed = parse(expr)
    dt = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = dt + timedelta(days=horizon_days)
    while dt < end:
        if dt.month not in parsed[3]:
            dt = (dt.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
            continue
        if not _day_ok(parsed, dt):
            dt = dt.replace(hour=0, minute=0) + timedelta(days=1)
            continue
        if dt.hour not in parsed[1]:
            dt = dt.replace(minute=0) + timedelta(hours=1)
            continue
        if _match_parsed(parsed, dt):
            return dt
        dt += timedelta(minutes=1)
    return None
