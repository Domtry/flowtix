"""Data readers for CSV, Excel, JSON, XML."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from .models import (
    CsvOptions,
    DataFormat,
    DataResult,
    ExcelOptions,
    JsonOptions,
    ReadRequest,
    XmlOptions,
)

logger = structlog.get_logger()

_READERS: dict[DataFormat, Any] = {}


def _register(fmt: DataFormat):
    def decorator(fn):
        _READERS[fmt] = fn
        return fn
    return decorator


def read_data(request: ReadRequest) -> DataResult:
    reader = _READERS.get(request.format)
    if not reader:
        raise ValueError(f"Unsupported format: {request.format}")
    df = reader(request)
    logger.info("data.read", format=request.format, rows=len(df), cols=len(df.columns))
    return _df_to_result(df)


def _df_to_result(df: pd.DataFrame) -> DataResult:
    data = df.where(df.notna(), None).to_dict(orient="records")
    return DataResult(
        row_count=len(df),
        column_count=len(df.columns),
        columns=list(df.columns),
        data=data,
        preview=data[:10],
    )


@_register(DataFormat.CSV)
def _read_csv(req: ReadRequest) -> pd.DataFrame:
    opts = req.csv_options or CsvOptions()
    return pd.read_csv(
        req.source,
        delimiter=opts.delimiter,
        encoding=opts.encoding,
        header=0 if opts.has_header else None,
        quotechar=opts.quote_char,
        skiprows=opts.skip_rows or None,
    )


@_register(DataFormat.EXCEL)
def _read_excel(req: ReadRequest) -> pd.DataFrame:
    opts = req.excel_options or ExcelOptions()
    return pd.read_excel(
        req.source,
        sheet_name=opts.sheet_name,
        header=0 if opts.has_header else None,
        skiprows=opts.skip_rows or None,
        engine=opts.engine,
    )


@_register(DataFormat.JSON)
def _read_json(req: ReadRequest) -> pd.DataFrame:
    opts = req.json_options or JsonOptions()
    path = Path(req.source)
    raw = json.loads(path.read_text(encoding=opts.encoding))

    if opts.json_path:
        for key in opts.json_path.split("."):
            if isinstance(raw, dict):
                raw = raw[key]
            elif isinstance(raw, list) and key.isdigit():
                raw = raw[int(key)]

    if isinstance(raw, list):
        return pd.DataFrame(raw)
    if isinstance(raw, dict):
        return pd.DataFrame([raw])
    raise ValueError(f"Cannot convert JSON value to DataFrame: {type(raw)}")


@_register(DataFormat.XML)
def _read_xml(req: ReadRequest) -> pd.DataFrame:
    opts = req.xml_options or XmlOptions()
    tree = ET.parse(req.source)
    root = tree.getroot()

    rows: list[dict[str, str]] = []
    for elem in root.iter(opts.row_tag):
        row = {}
        for child in elem:
            row[child.tag] = child.text or ""
        if row:
            rows.append(row)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)
