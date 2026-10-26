"""Tests for data writers — CSV, JSON, XML."""

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from services.data_engine.src.models import DataFormat, WriteRequest, XmlOptions
from services.data_engine.src.writers import write_data

SAMPLE = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]


def test_write_csv(tmp_path):
    dest = str(tmp_path / "out.csv")
    write_data(SAMPLE, WriteRequest(destination=dest, format=DataFormat.CSV))
    with open(dest) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["name"] == "Alice"


def test_write_json(tmp_path):
    dest = str(tmp_path / "out.json")
    write_data(SAMPLE, WriteRequest(destination=dest, format=DataFormat.JSON))
    data = json.loads(Path(dest).read_text())
    assert len(data) == 2
    assert data[1]["name"] == "Bob"


def test_write_xml(tmp_path):
    dest = str(tmp_path / "out.xml")
    write_data(SAMPLE, WriteRequest(
        destination=dest, format=DataFormat.XML,
        xml_options=XmlOptions(row_tag="person", root_tag="people"),
    ))
    tree = ET.parse(dest)
    persons = tree.findall("person")
    assert len(persons) == 2
