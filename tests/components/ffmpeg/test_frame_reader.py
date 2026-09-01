"""Tests for viseron.components.ffmpeg.frame_reader."""

from __future__ import annotations

import logging
import pickle
import queue
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from viseron.components.ffmpeg import stream
from viseron.components.ffmpeg.const import MAX_EMPTY_FRAMES
from viseron.components.ffmpeg.frame_reader import (
    FrameReaderConfig,
    frame_reader_logger_name,
    run_frame_reader,
)


class _FakeQueue(queue.Queue):
    """queue.Queue plus the close() that multiprocessing queues have.

    run_frame_reader calls frame_queue.close() on shutdown; a plain queue.Queue
    would raise AttributeError.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.closed = False

    def close(self) -> None:
        """Record that the queue was closed."""
        self.closed = True


def _config(**overrides) -> FrameReaderConfig:
    defaults = {
        "camera_identifier": "cam",
        "decoder_command": ["ffmpeg", "-i", "rtsp://x"],
        "segment_command": None,
        "frame_bytes_size": 4,
        "ffmpeg_loglevel": "error",
        "recoverable_errors": [],
        "sensitive_strings": ("hunter2",),
        "log_level": logging.INFO,
    }
    defaults.update(overrides)
    return FrameReaderConfig(**defaults)


def _enter_patches(stack: ExitStack) -> tuple[MagicMock, MagicMock]:
    """Patch the child process side effects, returning the pipe and os.kill mocks."""
    module = "viseron.components.ffmpeg.frame_reader"
    ffmpeg_pipe = stack.enter_context(patch(f"{module}.FFmpegPipe"))
    stack.enter_context(patch(f"{module}.enable_child_logging"))
    stack.enter_context(patch(f"{module}.setproctitle"))
    kill = stack.enter_context(patch(f"{module}.os.kill"))
    return ffmpeg_pipe, kill


def test_config_is_picklable() -> None:
    """The payload crosses a forkserver boundary, so it must pickle."""
    config = _config()
    assert pickle.loads(pickle.dumps(config)) == config  # noqa: S301


def test_frame_reader_logger_name_matches_the_parent_stream_logger() -> None:
    """The child must configure the level of the logger the parent named."""
    assert frame_reader_logger_name("cam") == f"{stream.__name__}.cam"


def test_reads_frames_until_capture_frames_clears() -> None:
    """Frames flow to the queue until the capture event clears."""
    capture_frames = MagicMock()
    capture_frames.is_set.side_effect = [True, True, False]
    decode_error = MagicMock()
    decode_error.is_set.return_value = False
    frame_queue = _FakeQueue(maxsize=2)

    with ExitStack() as stack:
        ffmpeg_pipe, kill = _enter_patches(stack)
        ffmpeg_pipe.return_value.read.return_value = b"1234"
        run_frame_reader(_config(), frame_queue, capture_frames, decode_error)

    assert frame_queue.get_nowait() == b"1234"
    assert frame_queue.get_nowait() == b"1234"
    assert frame_queue.closed is True
    ffmpeg_pipe.return_value.start.assert_called_once()
    ffmpeg_pipe.return_value.close.assert_called_once()
    kill.assert_called_once()


def test_sets_decode_error_when_pipe_exits() -> None:
    """An exited ffmpeg process must raise decode_error."""
    capture_frames = MagicMock()
    capture_frames.is_set.side_effect = [True, False]
    decode_error = MagicMock()
    decode_error.is_set.return_value = False
    frame_queue = _FakeQueue(maxsize=2)

    with ExitStack() as stack:
        ffmpeg_pipe, _ = _enter_patches(stack)
        ffmpeg_pipe.return_value.read.return_value = None
        ffmpeg_pipe.return_value.poll.return_value = 1
        run_frame_reader(_config(), frame_queue, capture_frames, decode_error)

    decode_error.set.assert_called_once()


def test_sets_decode_error_after_max_empty_frames() -> None:
    """Repeated empty reads must raise decode_error."""
    capture_frames = MagicMock()
    capture_frames.is_set.side_effect = [True] * MAX_EMPTY_FRAMES + [False]
    decode_error = MagicMock()
    decode_error.is_set.return_value = False
    frame_queue = _FakeQueue(maxsize=2)

    with ExitStack() as stack:
        ffmpeg_pipe, _ = _enter_patches(stack)
        ffmpeg_pipe.return_value.read.return_value = None
        ffmpeg_pipe.return_value.poll.return_value = None
        run_frame_reader(_config(), frame_queue, capture_frames, decode_error)

    decode_error.set.assert_called_once()
