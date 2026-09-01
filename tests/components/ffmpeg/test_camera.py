"""Tests for viseron.components.ffmpeg.camera."""

from __future__ import annotations

import logging
import multiprocessing as mp
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest

from viseron.components.ffmpeg.camera import Camera
from viseron.components.ffmpeg.const import (
    CONFIG_FFMPEG_LOGLEVEL,
    CONFIG_FFMPEG_RECOVERABLE_ERRORS,
    CONFIG_RECORD_ONLY,
    CONFIG_SUBSTREAM,
)
from viseron.components.ffmpeg.frame_reader import frame_reader_logger_name
from viseron.helpers.logs import refresh_child_log_levels
from viseron.watchdog.process_watchdog import ProcessWatchDog
from viseron.watchdog.thread_watchdog import ThreadWatchDog

if TYPE_CHECKING:
    from collections.abc import Iterator

LOGGER_NAME = frame_reader_logger_name("cam")


@pytest.fixture(name="camera")
def camera_fixture() -> Iterator[Camera]:
    """Return a camera with only what the frame reader methods need."""
    camera = object.__new__(Camera)
    camera._identifier = "cam"
    camera._logger = MagicMock()
    camera._mp_context = cast("mp.context.ForkServerContext", mp.get_context())
    camera._frame_queue = None  # type: ignore[assignment]
    camera._capture_frames = MagicMock()
    camera.decode_error = MagicMock()
    camera._frame_reader = None
    camera._frame_relay = None
    camera._check_segment_process_thread = None
    camera.stream = MagicMock()
    camera._config = {
        CONFIG_SUBSTREAM: None,
        CONFIG_FFMPEG_LOGLEVEL: "error",
        CONFIG_FFMPEG_RECOVERABLE_ERRORS: [],
        CONFIG_RECORD_ONLY: False,
    }

    registered_processes = ProcessWatchDog.registered_items[:]
    registered_threads = ThreadWatchDog.registered_items[:]
    try:
        yield camera
    finally:
        camera._stop_camera()
        ProcessWatchDog.registered_items[:] = registered_processes
        ThreadWatchDog.registered_items[:] = registered_threads
        logging.getLogger(LOGGER_NAME).setLevel(logging.NOTSET)


def test_create_frame_reader_registers_the_child_log_levels(camera: Camera) -> None:
    """A running frame reader must follow the log level of its camera."""
    frame_reader, _ = camera._create_frame_reader()
    child_log_levels = frame_reader._child_log_levels

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


def test_stop_camera_unregisters_the_child_log_levels(camera: Camera) -> None:
    """A stopped camera must not be kept alive by the registry."""
    camera._frame_reader, _ = camera._create_frame_reader()
    camera._frame_relay = MagicMock()
    child_log_levels = camera._frame_reader._child_log_levels

    camera._stop_camera()
    refresh_child_log_levels()

    assert (
        child_log_levels.wait_and_apply(  # type: ignore[attr-defined]
            timeout=0.01,
        )
        is False
    )
