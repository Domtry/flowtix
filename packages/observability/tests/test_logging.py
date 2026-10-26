"""Tests for structured logging setup."""

import logging
from packages.observability.src.logging import setup_logging


def test_setup_dev_logging():
    setup_logging(json_output=False, level="DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) >= 1


def test_setup_json_logging():
    setup_logging(json_output=True, level="INFO")
    root = logging.getLogger()
    assert root.level == logging.INFO
