"""FFmpeg frame reader, executed in a child process.

This module is the entrypoint of the frame reader child process. It deliberately
depends on nothing that reaches back into the running Viseron instance. Keeping it
this way means we can use the forkserver approach to save memory.
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import time
from dataclasses import dataclass
from queue import Full
from typing import TYPE_CHECKING

import setproctitle

from viseron.helpers.logs import UnhelpfullLogFilter, enable_child_logging

from .const import FFMPEG_LOGLEVELS, MAX_EMPTY_FRAMES
from .pipe import FFmpegPipe

if TYPE_CHECKING:
    from multiprocessing import Queue
    from multiprocessing.synchronize import Event


@dataclass(frozen=True)
class FrameReaderConfig:
    """Everything the frame reader child process needs, as plain picklable data."""

    camera_identifier: str
    decoder_command: list[str]
    segment_command: list[str] | None
    frame_bytes_size: int
    ffmpeg_loglevel: str
    recoverable_errors: list[str]
    sensitive_strings: tuple[str, ...]
    log_level: int


def run_frame_reader(
    config: FrameReaderConfig,
    frame_queue: Queue[bytes],  # pylint: disable=unsubscriptable-object
    capture_frames: Event,
    decode_error: Event,
) -> None:
    """Read frames from FFmpeg and put them on the queue."""
    setproctitle.setproctitle(f"viseron.camera.{config.camera_identifier}.read_frames")
    enable_child_logging(config.sensitive_strings, config.log_level)

    logger = logging.getLogger(
        f"viseron.components.ffmpeg.stream.{config.camera_identifier}"
    )
    logger.addFilter(UnhelpfullLogFilter(config.recoverable_errors))

    pipe = FFmpegPipe(
        config.camera_identifier,
        logger,
        FFMPEG_LOGLEVELS[config.ffmpeg_loglevel],
        decoder_command=config.decoder_command,
        segment_command=config.segment_command,
    )

    decode_error.clear()
    empty_frames = 0

    pipe.start()

    while capture_frames.is_set():
        if decode_error.is_set():
            time.sleep(5)
            logger.error("Restarting frame pipe")
            pipe.close()
            pipe.start()
            decode_error.clear()
            empty_frames = 0

        frame_bytes = pipe.read(config.frame_bytes_size)
        if frame_bytes:
            empty_frames = 0
            # Dont queue frames if consumer is not ready
            with contextlib.suppress(Full):
                frame_queue.put_nowait(frame_bytes)
            continue

        if pipe.poll() is not None:
            logger.error("Frame reader process has exited")
            decode_error.set()
            continue

        empty_frames += 1
        if empty_frames >= MAX_EMPTY_FRAMES:
            logger.error("Did not receive a frame")
            decode_error.set()

    pipe.close()
    frame_queue.close()
    logger.debug("Frame reader stopped")
    os.kill(os.getpid(), signal.SIGKILL)
