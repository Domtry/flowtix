"""Data engine models — format configs, validation rules, transform operations."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DataFormat(str, Enum):
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    XML = "xml"


class CsvOptions(BaseModel):
    delimiter: str = ","
    encoding: str = "utf-8"
    has_header: bool = True
    quote_char: str = '"'
    skip_rows: int = 0


class ExcelOptions(BaseModel):
    sheet_name: str | int = 0
    has_header: bool = True
    skip_rows: int = 0
    engine: str = "openpyxl"


class JsonOptions(BaseModel):
    encoding: str = "utf-8"
    json_path: str | None = None
    orient: str = "records"


class XmlOptions(BaseModel):
    encoding: str = "utf-8"
    row_tag: str = "row"
    root_tag: str = "data"


class ReadRequest(BaseModel):
    source: str
    format: DataFormat
    csv_options: CsvOptions | None = None
    excel_options: ExcelOptions | None = None
    json_options: JsonOptions | None = None
    xml_options: XmlOptions | None = None


class WriteRequest(BaseModel):
    destination: str
    format: DataFormat
    csv_options: CsvOptions | None = None
    excel_options: ExcelOptions | None = None
    json_options: JsonOptions | None = None
    xml_options: XmlOptions | None = None


class ValidationType(str, Enum):
    NOT_NULL = "not_null"
    UNIQUE = "unique"
    REGEX = "regex"
    RANGE = "range"
    IN_LIST = "in_list"
    TYPE_CHECK = "type_check"
    CUSTOM = "custom"


class ValidationRule(BaseModel):
    column: str
    type: ValidationType
    params: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class ValidationError(BaseModel):
    row: int | None = None
    column: str
    rule: ValidationType
    message: str
    value: Any = None


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ValidationError] = Field(default_factory=list)
    row_count: int = 0


class TransformType(str, Enum):
    FILTER = "filter"
    MAP = "map"
    RENAME = "rename"
    DROP = "drop"
    SORT = "sort"
    DEDUPLICATE = "deduplicate"
    AGGREGATE = "aggregate"
    MERGE = "merge"
    FILL_NULL = "fill_null"
    CAST = "cast"


class TransformOp(BaseModel):
    type: TransformType
    params: dict[str, Any] = Field(default_factory=dict)


class DataResult(BaseModel):
    row_count: int
    column_count: int
    columns: list[str]
    data: list[dict[str, Any]]
    preview: list[dict[str, Any]] = Field(default_factory=list)
