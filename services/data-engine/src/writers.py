"""Data writers for CSV, Excel, JSON, XML."""

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
    ExcelOptions,
    JsonOptions,
    WriteRequest,
    XmlOptions,
)

logger = structlog.get_logger()

_WRITERS: dict[DataFormat, Any] = {}


def _register(fmt: DataFormat):
    def decorator(fn):
        _WRITERS[fmt] = fn
        return fn
    return decorator


def write_data(data: list[dict[str, Any]], request: WriteRequest) -> str:
    writer = _WRITERS.get(request.format)
    if not writer:
        raise ValueError(f"Unsupported format: {request.format}")
    df = pd.DataFrame(data)
    writer(df, request)
    logger.info("data.write", format=request.format, rows=len(df), dest=request.destination)
    return request.destination


@_register(DataFormat.CSV)
def _write_csv(df: pd.DataFrame, req: WriteRequest) -> None:
    opts = req.csv_options or CsvOptions()
    df.to_csv(
        req.destination,
        sep=opts.delimiter,
        encoding=opts.encoding,
        index=False,
        quotechar=opts.quote_char,
    )


@_register(DataFormat.EXCEL)
def _write_excel(df: pd.DataFrame, req: WriteRequest) -> None:
    opts = req.excel_options or ExcelOptions()
    sheet = opts.sheet_name if isinstance(opts.sheet_name, str) else "Sheet1"
    df.to_excel(req.destination, sheet_name=sheet, index=False, engine=opts.engine)


@_register(DataFormat.JSON)
def _write_json(df: pd.DataFrame, req: WriteRequest) -> None:
    opts = req.json_options or JsonOptions()
    records = df.where(df.notna(), None).to_dict(orient=opts.orient)
    Path(req.destination).write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding=opts.encoding,
    )


@_register(DataFormat.XML)
def _write_xml(df: pd.DataFrame, req: WriteRequest) -> None:
    opts = req.xml_options or XmlOptions()
    root = ET.Element(opts.root_tag)
    for _, row in df.iterrows():
        elem = ET.SubElement(root, opts.row_tag)
        for col, val in row.items():
            child = ET.SubElement(elem, str(col))
            child.text = "" if pd.isna(val) else str(val)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(req.destination, encoding=opts.encoding, xml_declaration=True)
