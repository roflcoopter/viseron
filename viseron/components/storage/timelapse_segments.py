"""Encode timelapse frames to HLS segments on demand."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess as sp
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

from viseron.components.storage.const import (
    TIMELAPSE_SEGMENT_CACHE_MAX_BYTES,
    TIMELAPSE_SEGMENT_CACHE_MIN_AGE,
    TIMELAPSE_SEGMENT_ENCODE_TIMEOUT,
    TIMELAPSE_SEGMENT_ENCODE_WORKERS,
    TIMELAPSE_SEGMENT_MAX_PENDING_ENCODES,
    TIMELAPSE_STREAM_FPS,
)
from viseron.components.storage.queries import (
    TimelapseFrame,
    get_timelapse_frame_paths,
)
from viseron.helpers import create_directory

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

LOGGER = logging.getLogger(__name__)

# Frames at the end of a stream that are tried when deciding its size
STREAM_SIZE_CANDIDATES = 5


class TimelapseSegmentError(Exception):
    """Encoding a segment failed."""


class TimelapseSegmentBusyError(Exception):
    """Too many segment encodes are pending."""


@dataclass(frozen=True)
class SegmentRequest:
    """The frames of one segment and where it sits in its stream."""

    camera_identifier: str
    file_keys: tuple[int, ...]
    start_frame: int
    width: int
    height: int

    @property
    def cache_key(self) -> str:
        """Return a key that identifies the encoded segment."""
        return hashlib.sha256(repr(self).encode()).hexdigest()


def _even(value: float) -> int:
    return max(2, int(value) // 2 * 2)


def output_size(width: int, height: int, max_width: int | None) -> tuple[int, int]:
    """Return the even output size, downscaled to max_width if needed."""
    if max_width and width > max_width:
        height = round(height * max_width / width)
        width = max_width
    return _even(width), _even(height)


def video_filter(width: int, height: int) -> str:
    """Scale and pad frames to a fixed size.

    A fixed size keeps the stream decodable if the camera resolution changes
    mid-range.
    """
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease"
        ":out_range=tv,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,format=yuv420p"
    )


def read_frame(paths: list[str]) -> bytes | None:
    """Read the first of a frame's paths that exists, lowest tier first."""
    for path in paths:
        try:
            with open(path, "rb") as file:
                return file.read()
        except OSError:
            continue
    return None


def _frame_size(data: bytes) -> tuple[int, int] | None:
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        # cv2 stubs claim imdecode never returns None; it does on invalid data
        return None  # type: ignore[unreachable]
    height, width = image.shape[:2]
    return width, height


def _blank_frame(width: int, height: int) -> bytes:
    _, encoded = cv2.imencode(".jpg", np.zeros((height, width, 3), np.uint8))
    return encoded.tobytes()


def fill_missing(frames: list[bytes | None], blank: bytes) -> list[bytes]:
    """Replace missing frames so the segment keeps the duration of its playlist.

    A missing frame repeats the previous one, leading ones repeat the first
    readable frame.
    A frame can be missing if it has been deleted or moved after the playlist
    was built.
    """
    previous = next((frame for frame in frames if frame is not None), blank)
    filled: list[bytes] = []
    for frame in frames:
        if frame is not None:
            previous = frame
        filled.append(previous)
    return filled


def stream_size(
    camera_identifier: str,
    frames: list[TimelapseFrame],
    get_session: Callable[[], Session],
    max_width: int | None,
) -> tuple[int, int] | None:
    """Return the output size of a stream from its newest readable frame.

    The newest frames are used since the oldest are the first to be pruned.
    """
    candidates = frames[-STREAM_SIZE_CANDIDATES:][::-1]
    if not candidates:
        return None
    paths = get_timelapse_frame_paths(
        camera_identifier, [frame.file_key for frame in candidates], get_session
    )
    for frame in candidates:
        data = read_frame(paths.get(frame.file_key, []))
        size = _frame_size(data) if data else None
        if size:
            return output_size(*size, max_width)
    return None


def encode_segment(frames: list[bytes], output: str, request: SegmentRequest) -> None:
    """Encode JPEG frames to an MPEG-TS segment of the stream."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(TIMELAPSE_STREAM_FPS),
        "-c:v",
        "mjpeg",
        "-i",
        "-",
        "-vf",
        video_filter(request.width, request.height),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-g",
        str(len(frames)),
        # Without B-frames the timestamps of separately encoded segments line up
        "-bf",
        "0",
        "-output_ts_offset",
        str(request.start_frame / TIMELAPSE_STREAM_FPS),
        "-muxdelay",
        "0",
        "-muxpreload",
        "0",
        "-f",
        "mpegts",
        output,
    ]
    try:
        result = sp.run(
            cmd,
            input=b"".join(frames),
            stdout=sp.DEVNULL,
            stderr=sp.PIPE,
            timeout=TIMELAPSE_SEGMENT_ENCODE_TIMEOUT,
            check=False,
        )
    except sp.TimeoutExpired as error:
        raise TimelapseSegmentError("Encoding the segment timed out.") from error
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise TimelapseSegmentError(
            f"ffmpeg exited with code {result.returncode}: {stderr}"
        )


class TimelapseSegmentEncoder:
    """Encode segments on a bounded thread pool into a size-capped disk cache."""

    def __init__(
        self,
        cache_dir: str,
        max_bytes: int = TIMELAPSE_SEGMENT_CACHE_MAX_BYTES,
        max_pending: int = TIMELAPSE_SEGMENT_MAX_PENDING_ENCODES,
    ) -> None:
        self._cache_dir = cache_dir
        self._max_bytes = max_bytes
        self._max_pending = max_pending
        self._executor = ThreadPoolExecutor(
            max_workers=TIMELAPSE_SEGMENT_ENCODE_WORKERS,
            thread_name_prefix="timelapse_segment",
        )
        self._in_flight: dict[str, Future[str]] = {}
        self._lock = threading.Lock()
        shutil.rmtree(cache_dir, ignore_errors=True)
        create_directory(cache_dir)

    def get(
        self,
        request: SegmentRequest,
        get_session: Callable[[], Session],
        *,
        limit_pending: bool = True,
    ) -> Future[str]:
        """Return a future that resolves to the path of the encoded segment.

        Encodes outlive the request that started them since they are shared, so
        with limit_pending a new encode is rejected with TimelapseSegmentBusyError
        while too many are pending.
        """
        path = os.path.join(self._cache_dir, f"{request.cache_key}.ts")
        with self._lock:
            if request.cache_key in self._in_flight:
                return self._in_flight[request.cache_key]
            if os.path.exists(path):
                # Marks the segment as recently used for eviction
                os.utime(path)
                cached: Future[str] = Future()
                cached.set_result(path)
                return cached
            if limit_pending and len(self._in_flight) >= self._max_pending:
                raise TimelapseSegmentBusyError
            future = self._executor.submit(self._encode, request, path, get_session)
            self._in_flight[request.cache_key] = future
        future.add_done_callback(lambda _future: self._forget(request.cache_key))
        return future

    def _forget(self, cache_key: str) -> None:
        with self._lock:
            self._in_flight.pop(cache_key, None)

    def _encode(
        self,
        request: SegmentRequest,
        path: str,
        get_session: Callable[[], Session],
    ) -> str:
        paths = get_timelapse_frame_paths(
            request.camera_identifier, list(request.file_keys), get_session
        )
        frames = fill_missing(
            [read_frame(paths.get(file_key, [])) for file_key in request.file_keys],
            _blank_frame(request.width, request.height),
        )
        temp_path = f"{path}.{uuid.uuid4()}.tmp"
        try:
            encode_segment(frames, temp_path, request)
            os.replace(temp_path, path)
        finally:
            try:
                os.remove(temp_path)
            except FileNotFoundError:
                pass
        self._evict()
        return path

    def _evict(self) -> None:
        """Remove the least recently used segments until the cache fits."""
        with self._lock:
            entries: list[tuple[float, int, str]] = []
            for name in os.listdir(self._cache_dir):
                if not name.endswith(".ts"):
                    continue
                path = os.path.join(self._cache_dir, name)
                try:
                    stat = os.stat(path)
                except FileNotFoundError:
                    continue
                entries.append((stat.st_mtime, stat.st_size, path))
            total = sum(size for _, size, _ in entries)
            cutoff = time.time() - TIMELAPSE_SEGMENT_CACHE_MIN_AGE
            for mtime, size, path in sorted(entries):
                if total <= self._max_bytes or mtime > cutoff:
                    break
                os.remove(path)
                total -= size

    def stop(self) -> None:
        """Cancel queued encodes and wait for running ones to finish."""
        self._executor.shutdown(wait=True, cancel_futures=True)
