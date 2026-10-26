"""Data transformation pipeline — filter, map, rename, sort, aggregate, etc."""

from __future__ import annotations

from typing import Any

import pandas as pd
import structlog

from .models import DataResult, TransformOp, TransformType

logger = structlog.get_logger()

_TRANSFORMS: dict[TransformType, Any] = {}


def _register(ttype: TransformType):
    def decorator(fn):
        _TRANSFORMS[ttype] = fn
        return fn
    return decorator


def transform(data: list[dict[str, Any]], ops: list[TransformOp]) -> DataResult:
    df = pd.DataFrame(data)
    for op in ops:
        handler = _TRANSFORMS.get(op.type)
        if not handler:
            raise ValueError(f"Unknown transform: {op.type}")
        df = handler(df, op.params)
        logger.info("data.transform", op=op.type, rows=len(df))

    records = df.where(df.notna(), None).to_dict(orient="records")
    return DataResult(
        row_count=len(df),
        column_count=len(df.columns),
        columns=list(df.columns),
        data=records,
        preview=records[:10],
    )


@_register(TransformType.FILTER)
def _filter(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    column = params["column"]
    operator = params.get("operator", "eq")
    value = params["value"]
    ops = {
        "eq": lambda s: s == value,
        "ne": lambda s: s != value,
        "gt": lambda s: s > value,
        "gte": lambda s: s >= value,
        "lt": lambda s: s < value,
        "lte": lambda s: s <= value,
        "contains": lambda s: s.astype(str).str.contains(str(value), na=False),
        "startswith": lambda s: s.astype(str).str.startswith(str(value)),
    }
    return df[ops[operator](df[column])].reset_index(drop=True)


@_register(TransformType.MAP)
def _map(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    column = params["column"]
    mapping = params["mapping"]
    df[column] = df[column].map(lambda v: mapping.get(str(v), v))
    return df


@_register(TransformType.RENAME)
def _rename(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    return df.rename(columns=params.get("columns", {}))


@_register(TransformType.DROP)
def _drop(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    return df.drop(columns=params.get("columns", []), errors="ignore")


@_register(TransformType.SORT)
def _sort(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    by = params.get("by", [])
    ascending = params.get("ascending", True)
    return df.sort_values(by=by, ascending=ascending).reset_index(drop=True)


@_register(TransformType.DEDUPLICATE)
def _dedup(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    subset = params.get("columns") or None
    return df.drop_duplicates(subset=subset).reset_index(drop=True)


@_register(TransformType.AGGREGATE)
def _aggregate(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    group_by = params["group_by"]
    agg = params["agg"]
    return df.groupby(group_by).agg(agg).reset_index()


@_register(TransformType.FILL_NULL)
def _fill_null(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    column = params["column"]
    value = params["value"]
    df[column] = df[column].fillna(value)
    return df


@_register(TransformType.CAST)
def _cast(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    column = params["column"]
    dtype = params["dtype"]
    df[column] = df[column].astype(dtype)
    return df
