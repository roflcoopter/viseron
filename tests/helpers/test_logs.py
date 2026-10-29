"""Tests for logging setup."""

from __future__ import annotations

import logging
import multiprocessing as mp
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

import pytest

from viseron.helpers.logs import (
    NOISY_LOGGERS,
    ChildLogLevels,
    SensitiveInformationFilter,
    enable_child_logging,
    enable_logging,
    refresh_child_log_levels,
    register_child_log_levels,
    unregister_child_log_levels,
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


@pytest.fixture(name="temporary_loggers")
def temporary_loggers_fixture() -> Iterator[None]:
    """Remove loggers created by a test from the global logger registry."""
    existing = set(logging.Logger.manager.loggerDict)
    try:
        yield
    finally:
        for logger_name in set(logging.Logger.manager.loggerDict) - existing:
            del logging.Logger.manager.loggerDict[logger_name]


@pytest.mark.usefixtures("temporary_loggers")
def test_child_log_levels_applies_the_levels_resolved_in_the_parent() -> None:
    """A child restores the levels the parent resolved for it."""
    logging.getLogger("test_parent").setLevel(logging.DEBUG)
    child_log_levels = ChildLogLevels(mp.get_context(), ("test_parent",))

    # A forkserver child starts without the parents levels.
    logging.getLogger("test_parent").setLevel(logging.NOTSET)
    child_log_levels.apply()

    assert logging.getLogger("test_parent").level == logging.DEBUG


@pytest.mark.usefixtures("temporary_loggers")
def test_child_log_levels_wait_and_apply_picks_up_a_refreshed_level() -> None:
    """A level changed in the parent reaches the child without a restart."""
    logging.getLogger("test_parent").setLevel(logging.INFO)
    child_log_levels = ChildLogLevels(mp.get_context(), ("test_parent",))

    logging.getLogger("test_parent").setLevel(logging.DEBUG)
    child_log_levels.refresh()
    # The child is still on the level it started with.
    logging.getLogger("test_parent").setLevel(logging.INFO)

    assert child_log_levels.wait_and_apply(timeout=5) is True
    assert logging.getLogger("test_parent").level == logging.DEBUG


@pytest.mark.usefixtures("temporary_loggers")
def test_child_log_levels_wait_and_apply_times_out_when_nothing_changed() -> None:
    """A child that is not notified must not busy loop."""
    child_log_levels = ChildLogLevels(mp.get_context(), ("test_parent",))

    assert child_log_levels.wait_and_apply(timeout=0.01) is False


def _wait_for_level(logger_name: str, level: int, timeout: float = 5.0) -> int:
    """Return the level of a logger, waiting for it to reach the expected one."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if logging.getLogger(logger_name).level == level:
            break
        time.sleep(0.01)
    return logging.getLogger(logger_name).level


@pytest.mark.usefixtures("temporary_loggers")
def test_child_log_levels_start_applies_the_shared_levels() -> None:
    """A starting child applies the levels the parent resolved for it."""
    logging.getLogger("test_parent").setLevel(logging.DEBUG)
    child_log_levels = ChildLogLevels(mp.get_context(), ("test_parent",))

    # A forkserver child starts without the parents levels.
    logging.getLogger("test_parent").setLevel(logging.INFO)
    child_log_levels.start()

    assert logging.getLogger("test_parent").level == logging.DEBUG


def _report_levels(child_log_levels: ChildLogLevels, result_queue) -> None:
    """Child process entrypoint reporting its level now and after a refresh."""
    child_log_levels.start()
    result_queue.put(logging.getLogger("test_parent").level)
    result_queue.put(_wait_for_level("test_parent", logging.DEBUG))


@pytest.mark.usefixtures("temporary_loggers")
def test_child_log_levels_reach_a_running_child_process() -> None:
    """A level changed in the parent reaches a running child, without a restart."""
    mp_context = mp.get_context("forkserver")
    logging.getLogger("test_parent").setLevel(logging.INFO)
    child_log_levels = ChildLogLevels(mp_context, ("test_parent",))
    result_queue = mp_context.Queue()

    process = mp_context.Process(
        target=_report_levels, args=(child_log_levels, result_queue), daemon=True
    )
    process.start()
    try:
        assert result_queue.get(timeout=30) == logging.INFO

        logging.getLogger("test_parent").setLevel(logging.DEBUG)
        child_log_levels.refresh()

        assert result_queue.get(timeout=30) == logging.DEBUG
    finally:
        process.join(timeout=30)
        process.kill()


@pytest.mark.usefixtures("temporary_loggers")
def test_child_log_levels_watcher_thread_is_a_daemon() -> None:
    """A child must not be kept alive by its log level watcher."""
    thread = ChildLogLevels(mp.get_context(), ("test_parent",)).start()

    assert thread.daemon


def _report_level(child_log_levels: ChildLogLevels, result_queue) -> None:
    """Child process entrypoint reporting the level it started with."""
    child_log_levels.start()
    result_queue.put(logging.getLogger("test_parent").level)


@pytest.mark.usefixtures("temporary_loggers")
def test_child_log_levels_are_current_when_a_child_is_restarted() -> None:
    """The watchdog restarts a child with the arguments it was created with."""
    mp_context = mp.get_context("forkserver")
    logging.getLogger("test_parent").setLevel(logging.INFO)
    child_log_levels = ChildLogLevels(mp_context, ("test_parent",))
    result_queue = mp_context.Queue()

    logging.getLogger("test_parent").setLevel(logging.DEBUG)
    child_log_levels.refresh()

    process = mp_context.Process(
        target=_report_level, args=(child_log_levels, result_queue), daemon=True
    )
    process.start()
    try:
        assert result_queue.get(timeout=30) == logging.DEBUG
    finally:
        process.join(timeout=30)
        process.kill()


@pytest.fixture(name="registered_child_log_levels")
def registered_child_log_levels_fixture() -> Iterator[ChildLogLevels]:
    """Register log levels for a child, unregistering them afterwards."""
    child_log_levels = register_child_log_levels(
        "test_camera", mp.get_context(), ("test_parent",)
    )
    try:
        yield child_log_levels
    finally:
        unregister_child_log_levels("test_camera")


@pytest.mark.usefixtures("temporary_loggers")
def test_refresh_child_log_levels_pushes_new_levels_to_registered_children(
    registered_child_log_levels: ChildLogLevels,
) -> None:
    """A reload of the logger component reaches every running child."""
    logging.getLogger("test_parent").setLevel(logging.DEBUG)
    refresh_child_log_levels()
    # The child is still on the level it started with.
    logging.getLogger("test_parent").setLevel(logging.INFO)

    assert registered_child_log_levels.wait_and_apply(timeout=5) is True
    assert logging.getLogger("test_parent").level == logging.DEBUG


@pytest.mark.usefixtures("temporary_loggers")
def test_unregistered_children_are_not_refreshed(
    registered_child_log_levels: ChildLogLevels,
) -> None:
    """A stopped child must not be kept alive by the registry."""
    unregister_child_log_levels("test_camera")

    refresh_child_log_levels()

    assert registered_child_log_levels.wait_and_apply(timeout=0.01) is False


@pytest.mark.usefixtures("temporary_loggers", "registered_child_log_levels")
def test_registering_the_same_child_twice_replaces_the_first(
    registered_child_log_levels: ChildLogLevels,
) -> None:
    """A restarted child replaces its predecessor instead of leaking it."""
    replacement = register_child_log_levels(
        "test_camera", mp.get_context(), ("test_parent",)
    )

    refresh_child_log_levels()

    assert registered_child_log_levels.wait_and_apply(timeout=0.01) is False
    assert replacement.wait_and_apply(timeout=0.01) is True


@pytest.mark.usefixtures("temporary_loggers")
def test_child_log_levels_resolve_the_level_inherited_from_an_ancestor() -> None:
    """A logger without a level of its own must still reach the child correctly."""
    logging.getLogger("test_parent").setLevel(logging.DEBUG)
    child_log_levels = ChildLogLevels(mp.get_context(), ("test_parent.child",))

    child_log_levels.apply()

    assert logging.getLogger("test_parent.child").level == logging.DEBUG


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
