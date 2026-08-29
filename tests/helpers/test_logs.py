"""Tests for logging setup."""

from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

import pytest

from viseron.helpers.logs import (
    NOISY_LOGGERS,
    SensitiveInformationFilter,
    enable_child_logging,
    enable_logging,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture(name="restore_logging", autouse=True)
def restore_logging_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Restore the root logger and excepthooks after each test."""
    monkeypatch.setattr(
        "viseron.helpers.logs.VISERON_LOG_PATH", str(tmp_path / "viseron.log")
    )
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level
    original_excepthook = sys.excepthook
    original_thread_excepthook = threading.excepthook
    original_noisy_levels = {
        logger_name: logging.getLogger(logger_name).level
        for logger_name in NOISY_LOGGERS
    }
    try:
        yield
    finally:
        root_logger.handlers[:] = original_handlers
        root_logger.setLevel(original_level)
        sys.excepthook = original_excepthook
        threading.excepthook = original_thread_excepthook
        for logger_name, level in original_noisy_levels.items():
            logging.getLogger(logger_name).setLevel(level)


def test_enable_child_logging_seeds_sensitive_strings() -> None:
    """The child must redact the same strings the parent does."""
    try:
        enable_child_logging(("sensitive_string",), logging.INFO)
        assert "sensitive_string" in SensitiveInformationFilter.sensitive_strings
    finally:
        SensitiveInformationFilter.remove_sensitive_string("sensitive_string")


def test_enable_child_logging_replaces_handlers() -> None:
    """Exactly one stream handler and one rotating file handler."""
    enable_child_logging((), logging.DEBUG)
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 2


@pytest.mark.parametrize(
    "setup_logging",
    [
        pytest.param(enable_logging, id="parent"),
        pytest.param(lambda: enable_child_logging((), logging.INFO), id="child"),
    ],
)
def test_setup_logging_configures_the_same_things(setup_logging) -> None:
    """Parent and child get identical handlers, filters and logger levels."""
    setup_logging()

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO
    assert not root_logger.propagate

    stream_handler, file_handler = root_logger.handlers
    assert isinstance(stream_handler, logging.StreamHandler)
    assert isinstance(file_handler, RotatingFileHandler)
    for handler in (stream_handler, file_handler):
        assert any(
            isinstance(log_filter, SensitiveInformationFilter)
            for log_filter in handler.filters
        )

    for logger_name, level in NOISY_LOGGERS.items():
        assert logging.getLogger(logger_name).level == level

    assert sys.excepthook.__module__ == "viseron.helpers.logs"
    assert threading.excepthook.__module__ == "viseron.helpers.logs"


def test_enable_logging_rotates_the_log_file(tmp_path: Path) -> None:
    """The main process starts every run with a fresh log file."""
    log_path = tmp_path / "viseron.log"
    log_path.write_text("old log")

    enable_logging()

    assert (tmp_path / "viseron.log.1").read_text() == "old log"


def test_enable_child_logging_does_not_rotate_the_log_file(tmp_path: Path) -> None:
    """Children must not rotate the log file the parent already rotated."""
    log_path = tmp_path / "viseron.log"
    log_path.write_text("parent log")

    enable_child_logging((), logging.INFO)

    assert not (tmp_path / "viseron.log.1").exists()
    assert log_path.read_text() == "parent log"
