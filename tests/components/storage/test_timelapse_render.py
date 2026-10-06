"""Tests for the timelapse renderer."""

from __future__ import annotations

import datetime
import os
import subprocess as sp
import threading
from collections.abc import Iterator
from concurrent.futures import Future
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from viseron.components.storage.queries import TimelapseFrame, TimelapseFrames
from viseron.components.storage.timelapse_render import (
    TimelapseNoFramesError,
    TimelapseRenderBusyError,
    TimelapseRenderCancelled,
    TimelapseRenderer,
    TimelapseRenderError,
    TimelapseRenderManager,
    TimelapseRenderRequest,
)
from viseron.components.storage.timelapse_segments import (
    SegmentRequest,
    TimelapseSegmentError,
)

MODULE = "viseron.components.storage.timelapse_render"


def _frames(count: int) -> list[TimelapseFrame]:
    return [
        TimelapseFrame(
            file_key=file_key,
            path=f"/unused/{file_key}.jpg",
            orig_ctime=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        )
        for file_key in range(count)
    ]


def _request(max_width: int | None = None) -> TimelapseRenderRequest:
    return TimelapseRenderRequest(
        camera_identifier="test",
        start=0,
        end=60,
        fps=30,
        max_frames=100,
        max_width=max_width,
    )


class FakeFfmpeg:
    """Stand-in for the ffmpeg process that records what is piped to it."""

    def __init__(self, cmd: list[str], exit_code: int, broken_pipe: bool) -> None:
        self.cmd = cmd
        self.written: list[bytes] = []
        self.returncode: int | None = None
        self.killed = False
        self.wait_timeouts: list[float | None] = []
        self._exit_code = exit_code
        self.stdin = MagicMock()
        self.stdin.write.side_effect = (
            BrokenPipeError if broken_pipe else self.written.append
        )
        # ffmpeg creates the output file as soon as it starts
        with open(cmd[-1], "wb"):
            pass

    def poll(self) -> int | None:
        """Return the exit code, or None while running."""
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        """Exit the process, timing out on the first poll."""
        self.wait_timeouts.append(timeout)
        if not self.killed and len(self.wait_timeouts) == 1:
            raise sp.TimeoutExpired("ffmpeg", timeout or 0)
        self.returncode = -9 if self.killed else self._exit_code
        return self.returncode

    def kill(self) -> None:
        """Kill the process."""
        self.killed = True


class FfmpegFactory:
    """Creates FakeFfmpeg processes and keeps track of them."""

    def __init__(self) -> None:
        self.processes: list[FakeFfmpeg] = []
        self.exit_code = 0
        self.broken_pipe = False

    def __call__(self, cmd: list[str], **_kwargs: Any) -> FakeFfmpeg:
        """Start a fake ffmpeg process."""
        self.processes.append(FakeFfmpeg(cmd, self.exit_code, self.broken_pipe))
        return self.processes[-1]


class FakeSegmentEncoder:
    """Returns segments whose content names their first frame."""

    def __init__(self, tmp_path: Any) -> None:
        self.requests: list[SegmentRequest] = []
        self.error: Exception | None = None
        self.pending = False
        self._tmp_path = tmp_path

    def get(
        self, request: SegmentRequest, _get_session: Any, limit_pending: bool = True
    ) -> Future[str]:
        """Return a completed future for the segment."""
        assert not limit_pending
        self.requests.append(request)
        future: Future[str] = Future()
        if self.pending:
            return future
        if self.error:
            future.set_exception(self.error)
            return future
        path = self._tmp_path / f"segment{request.start_frame}.ts"
        path.write_bytes(f"segment{request.start_frame}".encode())
        future.set_result(str(path))
        return future


@pytest.fixture(name="ffmpeg")
def fixture_ffmpeg(tmp_path: Any) -> Iterator[FfmpegFactory]:
    """Patch ffmpeg and the temp dir."""
    factory = FfmpegFactory()
    with (
        patch(f"{MODULE}.sp.Popen", side_effect=factory),
        patch(f"{MODULE}.TEMP_DIR", str(tmp_path / "temp")),
        patch(f"{MODULE}.LogPipe"),
    ):
        yield factory


@pytest.fixture(name="segments")
def fixture_segments(tmp_path: Any) -> FakeSegmentEncoder:
    """Return a fake segment encoder."""
    return FakeSegmentEncoder(tmp_path)


def _render(
    segments: FakeSegmentEncoder,
    frames: list[TimelapseFrame],
    size: tuple[int, int] | None = (200, 100),
    on_status: Any = None,
    cancel_event: threading.Event | None = None,
    timeout: float = 60,
    max_width: int | None = None,
) -> str:
    with (
        patch(
            f"{MODULE}.get_timelapse_frames",
            return_value=TimelapseFrames(total=len(frames), step=None, frames=frames),
        ),
        patch(f"{MODULE}.stream_size", return_value=size),
    ):
        return TimelapseRenderer(
            _request(max_width),
            MagicMock(),
            on_status or MagicMock(),
            cancel_event or threading.Event(),
            segments,  # type: ignore[arg-type]
            timeout=timeout,
        ).render()


def test_render_joins_segments(
    ffmpeg: FfmpegFactory, segments: FakeSegmentEncoder
) -> None:
    """Segments of 60 frames are piped to ffmpeg in order and retimed."""
    output = _render(segments, _frames(130))

    assert [
        (r.start_frame, len(r.file_keys), r.width, r.height) for r in segments.requests
    ] == [(0, 60, 200, 100), (60, 60, 200, 100), (120, 10, 200, 100)]
    (process,) = ffmpeg.processes
    assert process.written == [b"segment0", b"segment60", b"segment120"]
    assert process.cmd[process.cmd.index("-itsscale") + 1] == "0.5"
    assert process.cmd[process.cmd.index("-c") + 1] == "copy"
    process.stdin.close.assert_called_once()
    assert output == process.cmd[-1]
    assert os.path.exists(output)


@pytest.mark.usefixtures("ffmpeg")
def test_render_sizes_to_max_width(segments: FakeSegmentEncoder) -> None:
    """The stream size is capped at the requested width."""
    with (
        patch(
            f"{MODULE}.get_timelapse_frames",
            return_value=TimelapseFrames(total=1, step=None, frames=_frames(1)),
        ),
        patch(f"{MODULE}.stream_size", return_value=(1280, 720)) as size,
    ):
        TimelapseRenderer(
            _request(1280),
            MagicMock(),
            MagicMock(),
            threading.Event(),
            segments,  # type: ignore[arg-type]
        ).render()

    assert size.call_args.args[3] == 1280


@pytest.mark.usefixtures("ffmpeg")
def test_render_reports_progress(segments: FakeSegmentEncoder) -> None:
    """Progress is reported per segment, then encoding."""
    on_status = MagicMock()

    _render(segments, _frames(3), on_status=on_status)

    assert [call.args[0] for call in on_status.call_args_list] == [
        {"status": "rendering", "frame": 3, "total_frames": 3, "progress": 100.0},
        {"status": "encoding"},
    ]


@pytest.mark.parametrize(
    "frames, size",
    [
        pytest.param([], (200, 100), id="no_frames_in_range"),
        pytest.param(_frames(1), None, id="no_readable_frames"),
    ],
)
def test_render_no_frames(
    ffmpeg: FfmpegFactory,
    segments: FakeSegmentEncoder,
    frames: list[TimelapseFrame],
    size: tuple[int, int] | None,
) -> None:
    """Rendering without readable frames fails before ffmpeg is started."""
    with pytest.raises(TimelapseNoFramesError):
        _render(segments, frames, size=size)

    assert not ffmpeg.processes


def test_render_cancel(ffmpeg: FfmpegFactory, segments: FakeSegmentEncoder) -> None:
    """Cancelling kills ffmpeg and removes the temp file."""
    cancel_event = threading.Event()

    with pytest.raises(TimelapseRenderCancelled):
        _render(
            segments,
            _frames(130),
            on_status=lambda _status: cancel_event.set(),
            cancel_event=cancel_event,
        )

    (process,) = ffmpeg.processes
    assert process.killed
    assert len(process.written) == 1
    assert not os.path.exists(process.cmd[-1])


def test_render_cancel_while_segment_pending(
    ffmpeg: FfmpegFactory, segments: FakeSegmentEncoder
) -> None:
    """Cancelling is honored while waiting for a queued segment encode."""
    segments.pending = True
    cancel_event = threading.Event()
    timer = threading.Timer(0.05, cancel_event.set)
    timer.start()

    with (
        patch(f"{MODULE}.POLL_INTERVAL", 0.01),
        pytest.raises(TimelapseRenderCancelled),
    ):
        _render(segments, _frames(2), cancel_event=cancel_event)

    timer.join()
    (process,) = ffmpeg.processes
    assert process.killed
    assert not process.written


@pytest.mark.parametrize(
    "timeout, exit_code, broken_pipe, segment_error, match",
    [
        pytest.param(-1, 0, False, None, "timed out", id="timeout"),
        pytest.param(60, 1, False, None, "exited with code 1", id="ffmpeg_failed"),
        pytest.param(60, 1, True, None, "exited unexpectedly", id="broken_pipe"),
        pytest.param(
            60,
            0,
            False,
            TimelapseSegmentError("ffmpeg output"),
            r"^Failed to encode timelapse segment\.$",
            id="segment_failed",
        ),
    ],
)
def test_render_error_removes_output(
    tmp_path: Any,
    ffmpeg: FfmpegFactory,
    segments: FakeSegmentEncoder,
    timeout: float,
    exit_code: int,
    broken_pipe: bool,
    segment_error: Exception | None,
    match: str,
) -> None:
    """A failed render raises and leaves no temp file behind."""
    ffmpeg.exit_code = exit_code
    ffmpeg.broken_pipe = broken_pipe
    segments.error = segment_error

    with pytest.raises(TimelapseRenderError, match=match):
        _render(segments, _frames(2), timeout=timeout)

    assert not os.listdir(tmp_path / "temp")


def test_manager_queues_and_stops() -> None:
    """Jobs beyond the worker count are queued up to a limit, stop cancels all."""
    started = threading.Semaphore(0)

    def _render_until_cancelled(self: TimelapseRenderer) -> str:
        started.release()
        self._cancel_event.wait()
        raise TimelapseRenderCancelled

    manager = TimelapseRenderManager(MagicMock())
    statuses: list[list[dict[str, Any]]] = [[], [], []]
    with (
        patch.object(TimelapseRenderer, "render", _render_until_cancelled),
        patch(f"{MODULE}.TIMELAPSE_MAX_QUEUED_RENDERS", 1),
    ):
        jobs = [
            manager.submit(_request(), MagicMock(), status.append)
            for status in statuses
        ]
        with pytest.raises(TimelapseRenderBusyError):
            manager.submit(_request(), MagicMock(), MagicMock())
        assert started.acquire(timeout=5)
        assert started.acquire(timeout=5)

        manager.stop()

    assert statuses == [[], [], [{"status": "queued"}]]
    assert jobs[2].future.cancelled()
    for job in jobs[:2]:
        with pytest.raises(TimelapseRenderCancelled):
            job.future.result()
