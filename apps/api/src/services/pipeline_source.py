"""Turn an uploaded Excel/CSV file into rows of text values the robot can type."""

import io
import math
import re
from datetime import date, datetime, time

import pandas as pd

MAX_ROWS = 10_000


class SourceError(ValueError):
    pass


def _cell_text(v: object) -> str:
    """Render a cell the way a user would type it."""
    if v is None:
        return ""
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        if v.is_integer():
            return str(int(v))  # Excel stores 4028 as 4028.0
        return str(v)
    if isinstance(v, pd.Timestamp):
        v = v.to_pydatetime()
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y") if v.time() == time(0) else v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    if v is pd.NaT:
        return ""
    return str(v).strip()


def parse_source(filename: str, content: bytes, sheet: str | None = None) -> tuple[list[str], list[dict]]:
    """Return (columns, rows). Every value is a string; blank cells are ''."""
    name = filename.lower()
    try:
        if name.endswith((".xlsx", ".xlsm", ".xls")):
            df = pd.read_excel(io.BytesIO(content), sheet_name=sheet or 0, dtype=object)
        elif name.endswith((".csv", ".txt")):
            text = None
            for enc in ("utf-8-sig", "cp1252"):
                try:
                    text = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if text is None:
                raise SourceError("Encodage du fichier CSV non reconnu")
            # dtype=str keeps leading zeros (codes, phone numbers); sep sniffed (; or ,)
            df = pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=str,
                             keep_default_na=False)
        else:
            raise SourceError("Format non supporté : utilisez .xlsx, .xls ou .csv")
    except SourceError:
        raise
    except ValueError as exc:  # e.g. unknown sheet name
        raise SourceError(str(exc)) from exc
    except Exception as exc:
        raise SourceError(f"Fichier illisible : {exc}") from exc

    df = df.dropna(how="all")
    columns = [str(c).strip() for c in df.columns]
    # pandas silently renames a repeated header "Nom" to "Nom.1"
    mangled = [c for c in columns if re.fullmatch(r"(.+)\.\d+", c) and c.rsplit(".", 1)[0] in columns]
    if len(set(columns)) != len(columns) or mangled:
        dup = mangled[0].rsplit(".", 1)[0] if mangled else ""
        raise SourceError(f"Deux colonnes portent le même nom{' : ' + dup if dup else ''}")
    if len(df) > MAX_ROWS:
        raise SourceError(f"Trop de lignes ({len(df)}), maximum {MAX_ROWS}")

    rows = []
    for record in df.itertuples(index=False, name=None):
        row = {col: _cell_text(v) for col, v in zip(columns, record)}
        if any(row.values()):
            rows.append(row)
    return columns, rows


def excel_sheets(content: bytes) -> list[str]:
    try:
        return list(pd.ExcelFile(io.BytesIO(content)).sheet_names)
    except Exception:
        return []
