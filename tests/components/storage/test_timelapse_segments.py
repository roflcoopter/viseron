"""Tests for the timelapse segment encoder."""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess as sp
import threading
from typing import Any
from unittest.mock import ANY, MagicMock, patch

import cv2
import numpy as np
import pytest

from viseron.components.storage.queries import TimelapseFrame
from viseron.components.storage.timelapse_segments import (
    SegmentRequest,
    TimelapseSegmentBusyError,
    TimelapseSegmentEncoder,
    TimelapseSegmentError,
    encode_segment,
    fill_missing,
    output_size,
    stream_size,
)

MODULE = "viseron.components.storage.timelapse_segments"


def _jpeg(width: int = 64, height: int = 48) -> bytes:
    _, encoded = cv2.imencode(".jpg", np.zeros((height, width, 3), np.uint8))
    return encoded.tobytes()


def _segment_request(
    file_keys: tuple[int, ...] = (1,),
    start_frame: int = 0,
    width: int = 64,
    height: int = 48,
) -> SegmentRequest:
    return SegmentRequest(
        camera_identifier="test",
        file_keys=file_keys,
        start_frame=start_frame,
        width=width,
        height=height,
    )


def _frame(file_key: int) -> TimelapseFrame:
    return TimelapseFrame(
        file_key=file_key,
        path=f"/unused/{file_key}.jpg",
        orig_ctime=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
    )


def _fake_encode(frames: list[bytes], output: str, _request: SegmentRequest) -> None:
    with open(output, "wb") as file:
        file.write(b"".join(frames))


@pytest.mark.parametrize(
    "width, height, max_width, expected",
    [
        pytest.param(1920, 1080, None, (1920, 1080), id="no_max_width"),
        pytest.param(1920, 1080, 1280, (1280, 720), id="downscaled"),
        pytest.param(640, 480, 1280, (640, 480), id="never_upscaled"),
        pytest.param(201, 101, None, (200, 100), id="odd_rounded_down_to_even"),
        pytest.param(1281, 721, 854, (854, 480), id="downscaled_to_even"),
    ],
)
def test_output_size(
    width: int, height: int, max_width: int | None, expected: tuple[int, int]
) -> None:
    """Output dimensions are even and never larger than max_width."""
    assert output_size(width, height, max_width) == expected


@pytest.mark.parametrize(
    "frames, expected",
    [
        pytest.param([b"a", b"b"], [b"a", b"b"], id="nothing_missing"),
        pytest.param([b"a", None, b"c"], [b"a", b"a", b"c"], id="repeats_previous"),
        pytest.param([None, None, b"c"], [b"c", b"c", b"c"], id="leading_use_first"),
        pytest.param([None, None], [b"blank", b"blank"], id="none_readable"),
    ],
)
def test_fill_missing(frames: list[bytes | None], expected: list[bytes]) -> None:
    """Missing frames are replaced so the segment keeps its duration."""
    assert fill_missing(frames, b"blank") == expected


@pytest.mark.parametrize(
    "readable_keys, expected",
    [
        pytest.param({2, 3}, (1280, 720), id="newest_readable"),
        pytest.param({2}, (1280, 720), id="newest_missing"),
        pytest.param(set(), None, id="none_readable"),
    ],
)
def test_stream_size(
    tmp_path: Any, readable_keys: set[int], expected: tuple[int, int] | None
) -> None:
    """The stream size comes from the newest readable frame."""
    paths: dict[int, list[str]] = {}
    for file_key in readable_keys:
        path = str(tmp_path / f"{file_key}.jpg")
        with open(path, "wb") as file:
            file.write(_jpeg(1920, 1080))
        paths[file_key] = [str(tmp_path / "gone.jpg"), path]

    with patch(f"{MODULE}.get_timelapse_frame_paths", return_value=paths):
        size = stream_size("test", [_frame(1), _frame(2), _frame(3)], MagicMock(), 1280)

    assert size == expected


def test_stream_size_no_frames() -> None:
    """A stream without frames has no size."""
    assert stream_size("test", [], MagicMock(), 1280) is None


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="needs ffprobe")
def test_encode_segment(tmp_path: Any) -> None:
    """Segments have the requested size and continue the stream's timestamps."""
    output = str(tmp_path / "segment.ts")

    encode_segment([_jpeg(100, 50)] * 3, output, _segment_request(start_frame=60))

    probe = json.loads(
        sp.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-count_frames",
                "-show_entries",
                "stream=width,height,nb_read_frames,start_time",
                "-of",
                "json",
                output,
            ],
            capture_output=True,
            check=True,
        ).stdout
    )["streams"][0]
    assert (probe["width"], probe["height"], probe["nb_read_frames"]) == (64, 48, "3")
    assert float(probe["start_time"]) == pytest.approx(4.0, abs=0.01)


@pytest.mark.parametrize(
    "run_result, match",
    [
        pytest.param(
            sp.CompletedProcess([], 1, b"", b"bad input"), "bad input", id="failed"
        ),
        pytest.param(sp.TimeoutExpired("ffmpeg", 60), "timed out", id="timeout"),
    ],
)
def test_encode_segment_errors(
    tmp_path: Any, run_result: sp.CompletedProcess | Exception, match: str
) -> None:
    """Ffmpeg failures raise TimelapseSegmentError."""
    with (
        patch(f"{MODULE}.sp.run", side_effect=[run_result]),
        pytest.raises(TimelapseSegmentError, match=match),
    ):
        encode_segment([_jpeg()], str(tmp_path / "segment.ts"), _segment_request())


def test_encoder_clears_cache_on_start(tmp_path: Any) -> None:
    """Segments left over from a previous run are removed."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "stale.ts").write_bytes(b"stale")

    encoder = TimelapseSegmentEncoder(str(cache_dir))
    encoder.stop()

    assert not os.listdir(cache_dir)


def test_encoder_reads_frames_and_caches(tmp_path: Any) -> None:
    """Frames are read from any tier, missing ones repeated, and the result cached."""
    frame_path = tmp_path / "1.jpg"
    frame_path.write_bytes(b"frame1")
    encoder = TimelapseSegmentEncoder(str(tmp_path / "cache"))

    with (
        patch(
            f"{MODULE}.get_timelapse_frame_paths",
            return_value={1: [str(tmp_path / "gone.jpg"), str(frame_path)]},
        ) as get_paths,
        patch(f"{MODULE}.encode_segment", side_effect=_fake_encode) as encode,
    ):
        first = encoder.get(_segment_request((1, 2)), MagicMock()).result(timeout=5)
        second = encoder.get(_segment_request((1, 2)), MagicMock()).result(timeout=5)
    encoder.stop()

    assert first == second
    assert encode.call_count == 1
    assert encode.call_args.args[0] == [b"frame1", b"frame1"]
    get_paths.assert_called_once_with("test", [1, 2], ANY)
    with open(first, "rb") as file:
        assert file.read() == b"frame1frame1"


def test_encoder_shares_in_flight_encodes(tmp_path: Any) -> None:
    """Concurrent requests for the same segment encode it once."""
    release = threading.Event()

    def _slow_encode(frames: list[bytes], output: str, request: SegmentRequest) -> None:
        release.wait(5)
        _fake_encode(frames, output, request)

    encoder = TimelapseSegmentEncoder(str(tmp_path / "cache"))
    with (
        patch(f"{MODULE}.get_timelapse_frame_paths", return_value={}),
        patch(f"{MODULE}.encode_segment", side_effect=_slow_encode) as encode,
    ):
        first = encoder.get(_segment_request(), MagicMock())
        second = encoder.get(_segment_request(), MagicMock())
        release.set()
        first.result(timeout=5)
    encoder.stop()

    assert first is second
    assert encode.call_count == 1


def test_encoder_rejects_when_busy(tmp_path: Any) -> None:
    """New encodes beyond max_pending are rejected unless the limit is skipped."""
    release = threading.Event()

    def _slow_encode(frames: list[bytes], output: str, request: SegmentRequest) -> None:
        release.wait(5)
        _fake_encode(frames, output, request)

    encoder = TimelapseSegmentEncoder(str(tmp_path / "cache"), max_pending=1)
    with (
        patch(f"{MODULE}.get_timelapse_frame_paths", return_value={}),
        patch(f"{MODULE}.encode_segment", side_effect=_slow_encode),
    ):
        pending = encoder.get(_segment_request(), MagicMock())
        # Joining an encode that is already pending is still allowed
        assert encoder.get(_segment_request(), MagicMock()) is pending
        with pytest.raises(TimelapseSegmentBusyError):
            encoder.get(_segment_request(start_frame=60), MagicMock())
        unlimited = encoder.get(
            _segment_request(start_frame=60), MagicMock(), limit_pending=False
        )
        release.set()
        pending.result(timeout=5)
        unlimited.result(timeout=5)
    encoder.stop()


def test_encoder_retries_failed_encode(tmp_path: Any) -> None:
    """A failed encode leaves no temp file behind and is encoded again next time."""
    cache_dir = tmp_path / "cache"

    def _partial_then_fail(
        frames: list[bytes], output: str, request: SegmentRequest
    ) -> None:
        _fake_encode(frames, output, request)
        raise TimelapseSegmentError("ffmpeg failed")

    attempts = iter([_partial_then_fail, _fake_encode])

    def _encode(frames: list[bytes], output: str, request: SegmentRequest) -> None:
        next(attempts)(frames, output, request)

    encoder = TimelapseSegmentEncoder(str(cache_dir))
    with (
        patch(f"{MODULE}.get_timelapse_frame_paths", return_value={}),
        patch(f"{MODULE}.encode_segment", side_effect=_encode) as encode,
    ):
        failed = encoder.get(_segment_request(), MagicMock())
        forgotten = threading.Event()
        # Runs after the encoder's own callback that forgets the in-flight encode
        failed.add_done_callback(lambda _future: forgotten.set())
        with pytest.raises(TimelapseSegmentError, match="ffmpeg failed"):
            failed.result(timeout=5)
        assert forgotten.wait(5)
        assert not os.listdir(cache_dir)
        path = encoder.get(_segment_request(), MagicMock()).result(timeout=5)
    encoder.stop()

    assert encode.call_count == 2
    assert os.listdir(cache_dir) == [os.path.basename(path)]


@pytest.mark.parametrize(
    "min_age, old_mtime, old_exists",
    [
        pytest.param(0, (0, 0), False, id="evicts_least_recently_used"),
        pytest.param(60, None, True, id="keeps_recently_used"),
    ],
)
def test_encoder_eviction(
    tmp_path: Any,
    min_age: int,
    old_mtime: tuple[int, int] | None,
    old_exists: bool,
) -> None:
    """The cache is trimmed oldest first, sparing segments that were just used."""
    frame_path = tmp_path / "1.jpg"
    frame_path.write_bytes(b"12345678")
    encoder = TimelapseSegmentEncoder(str(tmp_path / "cache"), max_bytes=10)

    with (
        patch(f"{MODULE}.TIMELAPSE_SEGMENT_CACHE_MIN_AGE", min_age),
        patch(
            f"{MODULE}.get_timelapse_frame_paths",
            return_value={1: [str(frame_path)]},
        ),
        patch(f"{MODULE}.encode_segment", side_effect=_fake_encode),
    ):
        old = encoder.get(_segment_request(start_frame=0), MagicMock()).result(5)
        os.utime(old, old_mtime)
        new = encoder.get(_segment_request(start_frame=60), MagicMock()).result(5)
    encoder.stop()

    assert os.path.exists(old) is old_exists
    assert os.path.exists(new)
