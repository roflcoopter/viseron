"""Render timelapse frames to a video."""

from __future__ import annotations

import concurrent.futures
import logging
import os
import subprocess as sp
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from viseron.components.storage.const import (
    TIMELAPSE_MAX_CONCURRENT_RENDERS,
    TIMELAPSE_MAX_QUEUED_RENDERS,
    TIMELAPSE_RENDER_TIMEOUT,
    TIMELAPSE_SEGMENT_FRAMES,
    TIMELAPSE_STREAM_FPS,
)
from viseron.components.storage.queries import TimelapseFrame, get_timelapse_frames
from viseron.components.storage.timelapse_segments import (
    SegmentRequest,
    TimelapseSegmentEncoder,
    TimelapseSegmentError,
    stream_size,
)
from viseron.const import TEMP_DIR
from viseron.helpers import create_directory
from viseron.helpers.logs import LogPipe

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

LOGGER = logging.getLogger(__name__)

PROGRESS_INTERVAL = 0.5
POLL_INTERVAL = 0.5

StatusCallback = Callable[[dict[str, Any]], None]


class TimelapseRenderCancelled(Exception):
    """The render was cancelled."""


class TimelapseRenderError(Exception):
    """The render failed."""


class TimelapseNoFramesError(TimelapseRenderError):
    """There are no readable frames in the requested range."""


class TimelapseRenderBusyError(Exception):
    """Too many renders are running or queued."""


@dataclass
class TimelapseRenderRequest:
    """Parameters of a timelapse render."""

    camera_identifier: str
    start: float
    end: float
    fps: int
    max_frames: int
    max_width: int | None


class TimelapseRenderer:
    """Render timelapse frames to an MP4 by joining encoded segments.

    The segments are the ones used for playback, so a render with the same frames
    and size as the player only has to remux them.
    """

    def __init__(
        self,
        request: TimelapseRenderRequest,
        get_session: Callable[[], Session],
        on_status_callback: StatusCallback,
        cancel_event: threading.Event,
        segment_encoder: TimelapseSegmentEncoder,
        timeout: float = TIMELAPSE_RENDER_TIMEOUT,
    ) -> None:
        self._request = request
        self._get_session = get_session
        self._on_status_callback = on_status_callback
        self._cancel_event = cancel_event
        self._segment_encoder = segment_encoder
        self._timeout = timeout
        self._deadline = 0.0
        self._last_progress = 0.0

    def render(self) -> str:
        """Render the video and return the path to the temporary MP4."""
        self._deadline = time.monotonic() + self._timeout
        frames = get_timelapse_frames(
            self._request.camera_identifier,
            self._request.start,
            self._request.end,
            self._request.max_frames,
            self._get_session,
        ).frames
        if not frames:
            raise TimelapseNoFramesError("No timelapse frames found.")
        size = stream_size(
            self._request.camera_identifier,
            frames,
            self._get_session,
            self._request.max_width,
        )
        if size is None:
            raise TimelapseNoFramesError("No readable timelapse frames found.")

        create_directory(TEMP_DIR)
        output = os.path.join(TEMP_DIR, f"timelapse-{uuid.uuid4()}.mp4")
        log_pipe = LogPipe(LOGGER, logging.ERROR)
        process: sp.Popen[bytes] | None = None
        try:
            process = self._start_ffmpeg(output, log_pipe)
            self._pipe_segments(process, frames, size)
            self._on_status_callback({"status": "encoding"})
            self._wait(process)
        except BaseException:
            if process and process.poll() is None:
                process.kill()
                process.wait()
            try:
                os.remove(output)
            except FileNotFoundError:
                pass
            raise
        finally:
            log_pipe.close()
        return output

    def _pipe_segments(
        self,
        process: sp.Popen[bytes],
        frames: list[TimelapseFrame],
        size: tuple[int, int],
    ) -> None:
        if process.stdin is None:
            raise TimelapseRenderError("ffmpeg was started without stdin.")
        try:
            for start in range(0, len(frames), TIMELAPSE_SEGMENT_FRAMES):
                self._check_abort()
                segment = frames[start : start + TIMELAPSE_SEGMENT_FRAMES]
                process.stdin.write(self._read_segment(segment, start, size))
                self._report_progress(start + len(segment), len(frames))
            process.stdin.close()
        except BrokenPipeError as error:
            raise TimelapseRenderError("ffmpeg exited unexpectedly.") from error

    def _read_segment(
        self, frames: list[TimelapseFrame], start_frame: int, size: tuple[int, int]
    ) -> bytes:
        future = self._segment_encoder.get(
            SegmentRequest(
                camera_identifier=self._request.camera_identifier,
                file_keys=tuple(frame.file_key for frame in frames),
                start_frame=start_frame,
                width=size[0],
                height=size[1],
            ),
            self._get_session,
            # Renders are already bounded by the render manager
            limit_pending=False,
        )
        while True:
            # The segment can be queued behind other encodes, so keep honoring
            # cancellation and the deadline while waiting for it
            self._check_abort()
            try:
                path = future.result(timeout=POLL_INTERVAL)
            except concurrent.futures.TimeoutError:
                continue
            except TimelapseSegmentError as error:
                LOGGER.error("Failed to encode timelapse segment: %s", error)
                raise TimelapseRenderError(
                    "Failed to encode timelapse segment."
                ) from error
            break
        with open(path, "rb") as file:
            return file.read()

    def _start_ffmpeg(self, output: str, log_pipe: LogPipe) -> sp.Popen[bytes]:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "mpegts",
            # Segments are encoded at the stream frame rate
            "-itsscale",
            str(TIMELAPSE_STREAM_FPS / self._request.fps),
            "-i",
            "-",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output,
        ]
        LOGGER.debug("Timelapse render command: %s", " ".join(cmd))
        return sp.Popen(  # type: ignore[call-overload]
            cmd, stdin=sp.PIPE, stdout=sp.DEVNULL, stderr=log_pipe
        )

    def _check_abort(self) -> None:
        if self._cancel_event.is_set():
            raise TimelapseRenderCancelled
        if time.monotonic() > self._deadline:
            raise TimelapseRenderError(
                f"Render timed out after {self._timeout} seconds."
            )

    def _wait(self, process: sp.Popen[bytes]) -> None:
        while True:
            self._check_abort()
            try:
                returncode = process.wait(timeout=POLL_INTERVAL)
            except sp.TimeoutExpired:
                continue
            if returncode != 0:
                raise TimelapseRenderError(f"ffmpeg exited with code {returncode}")
            return

    def _report_progress(self, frame: int, total_frames: int) -> None:
        now = time.monotonic()
        if frame != total_frames and now - self._last_progress < PROGRESS_INTERVAL:
            return
        self._last_progress = now
        self._on_status_callback(
            {
                "status": "rendering",
                "frame": frame,
                "total_frames": total_frames,
                "progress": round(frame / total_frames * 100, 1),
            }
        )


class TimelapseRenderJob:
    """A submitted timelapse render."""

    def __init__(self, future: Future[str], cancel_event: threading.Event) -> None:
        self.future = future
        self._cancel_event = cancel_event

    def cancel(self) -> None:
        """Cancel the render, killing ffmpeg if it is running."""
        self._cancel_event.set()
        self.future.cancel()


class TimelapseRenderManager:
    """Run timelapse renders on a dedicated, bounded thread pool."""

    def __init__(self, segment_encoder: TimelapseSegmentEncoder) -> None:
        self._segment_encoder = segment_encoder
        self._executor = ThreadPoolExecutor(
            max_workers=TIMELAPSE_MAX_CONCURRENT_RENDERS,
            thread_name_prefix="timelapse_render",
        )
        self._jobs: set[TimelapseRenderJob] = set()
        self._lock = threading.Lock()

    def submit(
        self,
        request: TimelapseRenderRequest,
        get_session: Callable[[], Session],
        on_status_callback: StatusCallback,
    ) -> TimelapseRenderJob:
        """Submit a render. The future resolves to the path of the rendered MP4.

        Raises TimelapseRenderBusyError if too many renders are already queued.
        """
        cancel_event = threading.Event()
        renderer = TimelapseRenderer(
            request,
            get_session,
            on_status_callback,
            cancel_event,
            self._segment_encoder,
        )
        with self._lock:
            if len(self._jobs) >= (
                TIMELAPSE_MAX_CONCURRENT_RENDERS + TIMELAPSE_MAX_QUEUED_RENDERS
            ):
                raise TimelapseRenderBusyError
            if len(self._jobs) >= TIMELAPSE_MAX_CONCURRENT_RENDERS:
                on_status_callback({"status": "queued"})
            job = TimelapseRenderJob(
                self._executor.submit(renderer.render), cancel_event
            )
            self._jobs.add(job)
        job.future.add_done_callback(lambda _future: self._discard(job))
        return job

    def _discard(self, job: TimelapseRenderJob) -> None:
        with self._lock:
            self._jobs.discard(job)

    def stop(self) -> None:
        """Cancel all renders and wait for them to exit."""
        with self._lock:
            jobs = list(self._jobs)
        for job in jobs:
            job.cancel()
        self._executor.shutdown(wait=True, cancel_futures=True)
