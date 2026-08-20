"""FFmpeg camera tests."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from viseron.components.ffmpeg.camera import Camera
from viseron.components.ffmpeg.const import (
    DEFAULT_RESTART_DELAY,
    MAX_RESTART_DELAY,
)

from tests.common import MockCamera


def _camera_with_failing_stream(read_values: list, iterations: int = 12) -> MockCamera:
    """Return a MockCamera whose stream never delivers frames."""
    camera = MockCamera(identifier="test_camera_identifier")
    camera.decode_error = threading.Event()
    camera._capture_frames = MagicMock()
    camera._capture_frames.is_set.side_effect = [True] * iterations + [False]
    camera._thread_stuck = False
    camera.stream = MagicMock()
    camera.stream.read.side_effect = read_values
    camera.stream.poll.return_value = 1
    camera._logger = MagicMock()
    camera._frame_queue = MagicMock()
    return camera


class TestCameraReadFrames:
    """Test the read_frames method."""

    def test_read_frames_backs_off_exponentially_on_repeated_failures(self) -> None:
        """A dead camera must retry less often instead of every 5 seconds."""
        camera = _camera_with_failing_stream([None] * 20, iterations=12)
        iterations = 12

        sleeps: list[float] = []

        def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        with (
            patch("viseron.components.ffmpeg.camera.os.kill"),
            patch("viseron.components.ffmpeg.camera.setproctitle.setproctitle"),
            patch(
                "viseron.components.ffmpeg.camera.time.sleep",
                side_effect=fake_sleep,
            ),
        ):
            Camera.read_frames(camera, camera._frame_queue)

        # First failure waits the base delay, then each consecutive failure
        # doubles the wait until it is capped at MAX_RESTART_DELAY.
        assert sleeps == [
            DEFAULT_RESTART_DELAY,
            10,
            20,
            40,
            MAX_RESTART_DELAY,
            MAX_RESTART_DELAY,
            MAX_RESTART_DELAY,
            MAX_RESTART_DELAY,
            MAX_RESTART_DELAY,
            MAX_RESTART_DELAY,
            MAX_RESTART_DELAY,
        ]
        assert camera.stream.start_pipe.call_count == iterations

    def test_read_frames_resets_backoff_on_success(self) -> None:
        """A successful frame must reset the backoff to its base delay."""
        reads = [
            None,
            None,
            b"frame",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ]
        camera = _camera_with_failing_stream(reads)

        sleeps: list[float] = []

        def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        with (
            patch("viseron.components.ffmpeg.camera.os.kill"),
            patch("viseron.components.ffmpeg.camera.setproctitle.setproctitle"),
            patch(
                "viseron.components.ffmpeg.camera.time.sleep",
                side_effect=fake_sleep,
            ),
        ):
            Camera.read_frames(camera, camera._frame_queue)

        # The frame at read #3 resets the backoff, so the wait after the next
        # failure is back to the base delay.
        assert sleeps == [
            DEFAULT_RESTART_DELAY,
            10,
            DEFAULT_RESTART_DELAY,
            10,
            20,
            40,
            MAX_RESTART_DELAY,
            MAX_RESTART_DELAY,
            MAX_RESTART_DELAY,
            MAX_RESTART_DELAY,
        ]
        camera._frame_queue.put_nowait.assert_called_once_with(b"frame")
