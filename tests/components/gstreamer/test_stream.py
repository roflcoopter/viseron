"""Tests for viseron.components.gstreamer.stream."""

from __future__ import annotations

import logging
import multiprocessing as mp
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from viseron.components.gstreamer.const import CONFIG_GSTREAMER_LOGLEVEL
from viseron.components.gstreamer.gst_process import gst_logger_names
from viseron.components.gstreamer.stream import RestartableProcess, Stream
from viseron.helpers.logs import (
    refresh_child_log_levels,
    unregister_child_log_levels,
)
from viseron.watchdog.process_watchdog import ProcessWatchDog

if TYPE_CHECKING:
    from collections.abc import Iterator


LOGGER_NAME = gst_logger_names("cam")[0]


@pytest.fixture(name="stream")
def stream_fixture() -> Iterator[object]:
    """Return a stream with only what the pipe methods need."""
    stream = object.__new__(Stream)
    stream._camera_identifier = "cam"
    stream._logger = MagicMock()
    stream._pipeline = MagicMock()
    stream._pipeline.build_pipeline.return_value = ["videotestsrc", "!", "fakesink"]
    stream._config = {CONFIG_GSTREAMER_LOGLEVEL: "warning"}
    stream._camera = MagicMock()
    stream._mp_context = mp.get_context()
    stream._frame_queue = MagicMock()
    stream._process_frames_proc = None
    stream._process_frames_proc_exit = MagicMock()
    registered_processes = ProcessWatchDog.registered_items[:]
    try:
        yield stream
    finally:
        ProcessWatchDog.registered_items[:] = registered_processes
        unregister_child_log_levels(stream.alias)
        logging.getLogger(LOGGER_NAME).setLevel(logging.NOTSET)


def _start_pipe(stream) -> object:
    """Start the pipe, without a child process, and return its shared log levels."""
    with patch.object(RestartableProcess, "start"):
        stream.start_pipe()
    return stream._process_frames_proc._child_log_levels


def test_start_pipe_registers_the_child_log_levels(stream) -> None:
    """A running GStreamer child must follow the log level of its camera."""
    child_log_levels = _start_pipe(stream)

    logging.getLogger(LOGGER_NAME).setLevel(logging.DEBUG)
    refresh_child_log_levels()
    # The child is still on the level it started with.
    logging.getLogger(LOGGER_NAME).setLevel(logging.INFO)

    assert (
        child_log_levels.wait_and_apply(  # type: ignore[attr-defined]
            timeout=5,
        )
        is True
    )
    assert logging.getLogger(LOGGER_NAME).level == logging.DEBUG


def test_close_pipe_unregisters_the_child_log_levels(stream) -> None:
    """A closed pipe must not be kept alive by the registry."""
    child_log_levels = _start_pipe(stream)

    stream.close_pipe()
    refresh_child_log_levels()

    assert (
        child_log_levels.wait_and_apply(  # type: ignore[attr-defined]
            timeout=0.01,
        )
        is False
    )
