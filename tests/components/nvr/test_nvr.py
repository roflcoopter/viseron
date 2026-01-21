"""Tests for NVR component."""
# pylint: disable=protected-access

import datetime
import logging
import time
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, Mock, patch

import numpy as np
import pytest

from viseron.components.nvr.const import (
    COMPONENT,
    DATA_NO_DETECTOR_RESULT,
    MOTION_DETECTOR,
    NO_DETECTOR,
    OBJECT_DETECTOR,
)
from viseron.components.nvr.nvr import EVENT_MOTION_DETECTOR_RESULT, NVR
from viseron.components.storage.models import TriggerTypes
from viseron.domains.camera import EventFrameBytesData
from viseron.domains.camera.recorder import ManualRecording
from viseron.events import Event
from viseron.helpers import utcnow
from viseron.watchdog.thread_watchdog import RestartableThread

from tests.common import MockCamera, MockMotionDetector, MockObjectDetector
from tests.conftest import MockViseron


class FakeTime:
    """Controlled clock for tests."""

    def __init__(self, start: datetime.datetime | None = None):
        if start is None:
            start = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
        self.now = start

    def advance(self, seconds: int):
        """Advance time by given seconds."""
        self.now += datetime.timedelta(seconds=seconds)


def patch_nvr_utcnow(monkeypatch, fake_time: FakeTime) -> None:
    """Patch utcnow used by the NVR module."""
    monkeypatch.setattr("viseron.components.nvr.nvr.utcnow", lambda: fake_time.now)


def configure_camera_for_recording_tests(
    camera: MagicMock,
    fake_time: FakeTime,
    *,
    idle_timeout: int = 2,
) -> None:
    """Prep camera for recording tests."""
    camera.is_recording = False
    camera.recorder.idle_timeout = idle_timeout
    camera.recorder.max_recording_time_exceeded = False
    camera.recorder.active_recording = None
    camera.shared_frames = MagicMock()
    camera.shared_frames.get_decoded_frame_rgb.return_value = np.zeros(
        (2, 2, 3), dtype=np.uint8
    )
    camera.shared_frames.remove = MagicMock()

    def start_recorder_side_effect(_shared_frame, _objects_in_fov, trigger_type):
        camera.is_recording = True
        camera.recorder.active_recording = SimpleNamespace(
            start_time=fake_time.now, trigger_type=trigger_type
        )

    def stop_recorder_side_effect():
        camera.is_recording = False
        camera.recorder.active_recording = None

    camera.start_recorder.side_effect = start_recorder_side_effect
    camera.stop_recorder.side_effect = stop_recorder_side_effect


def safe_put(queue, item) -> None:
    """Put item into queue, removing oldest if full."""
    try:
        queue.put_nowait(item)
    except Exception:  # pylint: disable=broad-except
        try:
            queue.get_nowait()
        except Exception:  # pylint: disable=broad-except
            pass
        queue.put_nowait(item)


def feed_frame_to_nvr(nvr) -> None:
    """Queue frame + scanner tokens."""
    for scanner in nvr._frame_scanners.values():  # pylint: disable=protected-access
        safe_put(scanner.result_queue, object())
    frame = Event(
        "dummy",
        EventFrameBytesData(
            camera_identifier=nvr._camera.identifier,
            shared_frame=SimpleNamespace(  # type: ignore[arg-type]
                name="dummy_frame",
                capture_time=time.time(),
            ),
        ),
        utcnow().timestamp(),
    )
    nvr._frame_queue.put_nowait(frame)


def make_nvr(
    vis,
    *,
    camera_output_fps=10,
    object_detector=None,
    motion_detector=None,
):
    """Create NVR instance."""
    camera = MockCamera(
        vis=vis,
        output_fps=camera_output_fps,
    )

    with patch(
        "viseron.components.nvr.nvr.OperationStateSensor", return_value=MagicMock()
    ), patch(
        "viseron.components.nvr.nvr.RestartableThread",
        return_value=MagicMock(spec=RestartableThread),
    ):
        nvr = NVR(
            vis=vis,
            config={},
            camera_identifier=camera.identifier,
            object_detector=object_detector or False,
            motion_detector=motion_detector or False,
        )
    nvr.stop_recorder = Mock(  # type: ignore[method-assign]
        side_effect=nvr.stop_recorder,
    )
    return nvr, camera


class TestNVRInit:
    """Init tests."""

    def test_init_no_detectors_creates_no_detector_scanner(self, vis):
        """No detectors -> NO_DETECTOR scanner."""
        nvr, cam = make_nvr(vis)

        assert NO_DETECTOR in nvr._frame_scanners
        assert OBJECT_DETECTOR not in nvr._frame_scanners
        assert MOTION_DETECTOR not in nvr._frame_scanners

        # No detector scanner exists but is not scanning by default
        assert nvr._frame_scanners[NO_DETECTOR].scan is False

        # Subscribed to camera bytes and result topic
        vis.listen_event.assert_any_call(cam.frame_bytes_topic, ANY)
        vis.listen_event.assert_any_call(
            DATA_NO_DETECTOR_RESULT.format(camera_identifier=cam.identifier),
            ANY,
        )

        # Camera started and NVR registered
        cam.start_camera.assert_called_once()
        assert vis.data[COMPONENT][cam.identifier] is nvr

    def test_init_object_only_scanner_enabled(self, vis):
        """Object only -> object scan on."""
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        nvr, _ = make_nvr(vis, object_detector=object_detector)

        assert OBJECT_DETECTOR in nvr._frame_scanners
        assert nvr._frame_scanners[OBJECT_DETECTOR].scan is True
        assert MOTION_DETECTOR not in nvr._frame_scanners
        assert NO_DETECTOR not in nvr._frame_scanners

    def test_init_motion_only_scanner_enabled(self, vis: MockViseron):
        """Motion only -> motion scan on."""
        motion_detector = MockMotionDetector(fps=5, trigger_event_recording=True)
        nvr, cam = make_nvr(vis, motion_detector=motion_detector)

        assert MOTION_DETECTOR in nvr._frame_scanners
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is True

        # Subscribed to motion result topic
        vis.listen_event.assert_any_call(
            EVENT_MOTION_DETECTOR_RESULT.format(camera_identifier=cam.identifier),
            ANY,
        )

    def test_init_both_scan_on_motion_only_true(self, vis):
        """Both with motion-only -> motion on object off."""
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=True)
        motion_detector = MockMotionDetector(fps=5, trigger_event_recording=True)
        nvr, _ = make_nvr(
            vis, object_detector=object_detector, motion_detector=motion_detector
        )

        assert nvr._frame_scanners[MOTION_DETECTOR].scan is True
        assert nvr._frame_scanners[OBJECT_DETECTOR].scan is False

    @pytest.mark.parametrize(
        "trigger_event_recording,expected_motion_scan", [(True, True), (False, False)]
    )
    def test_init_both_scan_on_motion_only_false_motion_trigger_flag(
        self, vis, trigger_event_recording, expected_motion_scan
    ):
        """Both -> object on, motion per flag."""
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        motion_detector = MockMotionDetector(
            fps=5, trigger_event_recording=trigger_event_recording
        )
        nvr, _ = make_nvr(
            vis, object_detector=object_detector, motion_detector=motion_detector
        )

        assert nvr._frame_scanners[OBJECT_DETECTOR].scan is True
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is expected_motion_scan

    def test_init_scanner_fps_above_output_logs_warning_and_clamps_interval(
        self, vis, caplog
    ):
        """Scanner fps > output fps should warn and clamp scan interval to 1."""
        object_detector = MockObjectDetector(fps=20, scan_on_motion_only=False)
        nvr, _cam = make_nvr(
            vis,
            camera_output_fps=5,
            object_detector=object_detector,
        )

        scanner = nvr._frame_scanners[OBJECT_DETECTOR]
        assert scanner.scan_interval == 1  # 5/5 after clamping scan_fps to output_fps

        # Warning logged about FPS too high
        warnings = [
            rec.message
            for rec in caplog.records
            if rec.levelno == logging.WARNING
            and "FPS for object_detector is too high" in rec.message
        ]
        assert warnings, "Expected warning about FPS too high for object detector"

    def test_init_object_filter_requires_motion_without_motion_detector(
        self, vis, caplog
    ):
        """require_motion disabled and warning logged if no motion detector."""
        caplog.set_level(logging.WARNING, logger="viseron.components.nvr.nvr")
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        object_detector.object_filters = {
            "person": SimpleNamespace(require_motion=True)
        }
        make_nvr(vis, object_detector=object_detector)
        assert object_detector.object_filters["person"].require_motion is False
        warnings = [
            rec.message
            for rec in caplog.records
            if "requires motion detection, but motion detector is not configured"
            in rec.message
        ]
        assert warnings, "Expected warning about require_motion without motion detector"


class TestNVRRunMotionOnly:
    """_run tests (motion only)."""

    def test_run_motion_countdown_resets_on_new_motion(
        self, vis, monkeypatch, caplog: pytest.LogCaptureFixture
    ):
        """Motion countdown reset."""
        caplog.set_level(logging.DEBUG)
        motion_detector = MockMotionDetector(
            fps=5, trigger_event_recording=True, recorder_keepalive=True
        )
        nvr, camera = make_nvr(
            vis, camera_output_fps=5, motion_detector=motion_detector
        )

        # Configure camera and time control
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # Start recording with motion
        motion_detector.motion_detected = True
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording
        assert nvr._stop_recorder_at is None

        # Motion stops -> countdown starts at full idle_timeout
        caplog.clear()
        motion_detector.motion_detected = False
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._stop_recorder_at is not None
        assert nvr._seconds_left == 2  # type: ignore[unreachable]
        assert "Stopping recording in: 2s" in caplog.text

        # Advance 1s -> countdown decremented
        fake_time.advance(1)
        caplog.clear()
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._stop_recorder_at is not None
        assert nvr._seconds_left == 1
        assert "Stopping recording in: 1s" in caplog.text

        # Motion resumes -> countdown should reset (stop_recorder_at cleared)
        motion_detector.motion_detected = True
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._stop_recorder_at is None

        # Motion stops again -> countdown restarts from full idle_timeout
        caplog.clear()
        motion_detector.motion_detected = False
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._stop_recorder_at is not None
        assert nvr._seconds_left == 2
        assert "Stopping recording in: 2s" in caplog.text

        # Advance to timeout -> recording stops
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert not camera.is_recording
        camera.stop_recorder.assert_called()


class TestNVRRunObjectOnly:
    """_run tests (object only)."""

    def test_run_object_start_and_stop_with_idle_timeout(
        self, vis, monkeypatch, caplog: pytest.LogCaptureFixture
    ):
        """Object start/stop idle timeout."""
        caplog.set_level(logging.DEBUG)
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        nvr, camera = make_nvr(
            vis, camera_output_fps=5, object_detector=object_detector
        )

        # Configure camera and time control
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # 1) First frame: no objects -> no recording
        object_detector.objects_in_fov = []
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert not camera.is_recording
        camera.start_recorder.assert_not_called()

        # 2) Second frame: object detected -> recording starts
        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        camera.start_recorder.assert_called_once()
        assert nvr._stop_recorder_at is None

        # 3) Third frame: object disappears -> countdown to idle_timeout begins
        caplog.clear()
        object_detector.objects_in_fov = []
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._stop_recorder_at is not None
        assert nvr._seconds_left == 2  # type: ignore[unreachable]
        assert "Stopping recording in: 2s" in caplog.text

        # 4) Fourth frame: object still gone -> countdown continues
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._seconds_left == 1
        assert "Stopping recording in: 1s" in caplog.text

        # 5) Fifth frame: object still gone -> recording stops after timeout
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording is False
        assert nvr._stop_recorder_at is None
        assert nvr._seconds_left == 0
        assert "Stopping recording in: 0s" in caplog.text
        camera.stop_recorder.assert_called()

    def test_run_object_countdown_resets_on_new_object(
        self, vis, monkeypatch, caplog: pytest.LogCaptureFixture
    ):
        """Object countdown reset."""
        caplog.set_level(logging.DEBUG)
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        nvr, camera = make_nvr(
            vis, camera_output_fps=5, object_detector=object_detector
        )

        # Configure camera and time control
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # Start recording with an object
        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording
        assert nvr._stop_recorder_at is None

        # Object disappears -> countdown starts
        caplog.clear()
        object_detector.objects_in_fov = []
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._stop_recorder_at is not None
        assert nvr._seconds_left == 2  # type: ignore[unreachable]
        assert "Stopping recording in: 2s" in caplog.text

        # Advance 1s -> countdown decremented
        fake_time.advance(1)
        caplog.clear()
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._seconds_left == 1
        assert "Stopping recording in: 1s" in caplog.text

        # Object appears again -> countdown should reset (stop_recorder_at cleared)
        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._stop_recorder_at is None

        # Object disappears again -> countdown restarts from full idle_timeout
        caplog.clear()
        object_detector.objects_in_fov = []
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._stop_recorder_at is not None
        assert nvr._seconds_left == 2
        assert "Stopping recording in: 2s" in caplog.text

        # Advance to timeout -> recording stops
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert not camera.is_recording
        camera.stop_recorder.assert_called()

    def test_run_object_max_recording_timeout_exceeded(
        self, vis, monkeypatch, caplog: pytest.LogCaptureFixture
    ):
        """Object countdown reset."""
        caplog.set_level(logging.DEBUG)
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        nvr, camera = make_nvr(
            vis, camera_output_fps=5, object_detector=object_detector
        )

        # Configure camera and time control
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # Start recording with an object
        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording
        assert nvr._stop_recorder_at is None

        # Advance time indefinitely -> recording continues
        for _ in range(1, 6):
            fake_time.advance(1)
            feed_frame_to_nvr(nvr)
            nvr._run()
            assert camera.is_recording

        # Max recording time exceeded -> recording stops
        camera.recorder.max_recording_time_exceeded = True
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert "Max recording time exceeded, stopping recorder" in caplog.text
        assert nvr.stop_recorder.called_once_with(True)
        assert not camera.is_recording


class TestNVRRunBoth:
    """_run tests (both detectors)."""

    def test_both_initial_scanners_and_toggle_on_recording_then_pause_on_stop(
        self, vis, monkeypatch, caplog: pytest.LogCaptureFixture
    ):
        """Both scanners toggle."""
        caplog.set_level(logging.DEBUG)
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        motion_detector = MockMotionDetector(
            fps=5, trigger_event_recording=False, recorder_keepalive=True
        )
        nvr, camera = make_nvr(
            vis,
            camera_output_fps=5,
            object_detector=object_detector,
            motion_detector=motion_detector,
        )

        # Initial scanner states
        assert nvr._frame_scanners[OBJECT_DETECTOR].scan is True
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is False

        # Configure camera and time
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # Start recording due to object detection
        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording
        # Motion scanner should start due to recorder_keepalive
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is True

        # Objects gone and no motion -> countdown begins
        object_detector.objects_in_fov = []  # type: ignore[unreachable]
        motion_detector.motion_detected = False
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr._stop_recorder_at is not None

        # Complete countdown and stop
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()

        assert not camera.is_recording
        # Motion scanner should be paused after stopping
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is False

    def test_both_motion_keepalive_extends_recording_until_motion_stops(
        self, vis, monkeypatch, caplog: pytest.LogCaptureFixture
    ):
        """Keepalive extends until motion ends."""
        caplog.set_level(logging.DEBUG)
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        motion_detector = MockMotionDetector(
            fps=5, trigger_event_recording=False, recorder_keepalive=True
        )
        nvr, camera = make_nvr(
            vis,
            camera_output_fps=5,
            object_detector=object_detector,
            motion_detector=motion_detector,
        )

        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # Start via object
        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is True

        # Objects gone, motion present -> keepalive active (no countdown)
        object_detector.objects_in_fov = []
        motion_detector.motion_detected = True
        for _ in range(3):
            feed_frame_to_nvr(nvr)
            nvr._run()
            assert camera.is_recording
            assert nvr._stop_recorder_at is None

        # Motion stops -> countdown begins
        motion_detector.motion_detected = False
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr._stop_recorder_at is not None

        # Stop after idle timeout
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert not camera.is_recording
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is False

    def test_both_motion_keepalive_capped_by_max_recorder_keepalive(
        self, vis, monkeypatch, caplog: pytest.LogCaptureFixture
    ):
        """Keepalive capped."""
        caplog.set_level(logging.DEBUG)
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        motion_detector = MockMotionDetector(
            fps=5,
            trigger_event_recording=False,
            recorder_keepalive=True,
            max_recorder_keepalive=1,
        )
        nvr, camera = make_nvr(
            vis,
            camera_output_fps=5,
            object_detector=object_detector,
            motion_detector=motion_detector,
        )

        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # Start via object
        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is True

        # Objects gone, motion stays -> after ~1s (5 frames) countdown should begin
        object_detector.objects_in_fov = []
        motion_detector.motion_detected = True
        for _ in range(6):
            feed_frame_to_nvr(nvr)
            nvr._run()
        assert nvr._stop_recorder_at is not None

        # Finish countdown even though motion still detected
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert not camera.is_recording
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is False

    def test_both_countdown_resets_on_object_or_motion(
        self, vis, monkeypatch, caplog: pytest.LogCaptureFixture
    ):
        """Countdown reset by object/motion."""
        caplog.set_level(logging.DEBUG)
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        motion_detector = MockMotionDetector(
            fps=5, trigger_event_recording=False, recorder_keepalive=True
        )
        nvr, camera = make_nvr(
            vis,
            camera_output_fps=5,
            object_detector=object_detector,
            motion_detector=motion_detector,
        )

        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # Start via object
        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is True

        # Remove all -> start countdown
        object_detector.objects_in_fov = []
        motion_detector.motion_detected = False
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr._stop_recorder_at is not None
        assert nvr._seconds_left == 2

        # Advance 1s -> seconds_left becomes 1
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr._seconds_left == 1

        # Reset by object reappearing
        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr._stop_recorder_at is None

        # Remove object again -> countdown restarts from full timeout
        object_detector.objects_in_fov = []
        caplog.clear()
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr._seconds_left == 2
        assert "Stopping recording in: 2s" in caplog.text

        # Reset by motion starting
        motion_detector.motion_detected = True
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr._stop_recorder_at is None

        # Remove motion -> countdown restarts again from full timeout
        motion_detector.motion_detected = False
        caplog.clear()
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr._seconds_left == 2
        assert "Stopping recording in: 2s" in caplog.text

        # Finish countdown
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert "Stopping recording in: 1s" in caplog.text
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert not camera.is_recording
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is False

    def test_require_motion_blocks_start_without_motion(self, vis, monkeypatch):
        """require_motion blocks start until motion."""
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        motion_detector = MockMotionDetector(
            fps=5, trigger_event_recording=False, recorder_keepalive=True
        )
        object_detector.object_filters = {
            "person": SimpleNamespace(require_motion=True)
        }
        nvr, camera = make_nvr(
            vis,
            camera_output_fps=5,
            object_detector=object_detector,
            motion_detector=motion_detector,
        )

        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        motion_detector.motion_detected = False
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert not camera.is_recording

        motion_detector.motion_detected = True
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert nvr._frame_scanners[MOTION_DETECTOR].scan is True

    def test_require_motion_stops_when_motion_lost(self, vis, monkeypatch):
        """Stops via countdown when motion lost."""
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        motion_detector = MockMotionDetector(
            fps=5, trigger_event_recording=False, recorder_keepalive=True
        )
        object_detector.object_filters = {
            "person": SimpleNamespace(require_motion=True)
        }
        nvr, camera = make_nvr(
            vis,
            camera_output_fps=5,
            object_detector=object_detector,
            motion_detector=motion_detector,
        )

        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        motion_detector.motion_detected = True
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording

        motion_detector.motion_detected = False
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr._stop_recorder_at is not None

        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert not camera.is_recording

    def test_require_motion_keepalive_when_object_gone_motion_present(
        self, vis, monkeypatch
    ):
        """Keepalive holds after object disappears."""
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        motion_detector = MockMotionDetector(
            fps=5, trigger_event_recording=False, recorder_keepalive=True
        )
        object_detector.object_filters = {
            "person": SimpleNamespace(require_motion=True)
        }
        nvr, camera = make_nvr(
            vis,
            camera_output_fps=5,
            object_detector=object_detector,
            motion_detector=motion_detector,
        )

        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        motion_detector.motion_detected = True
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording

        object_detector.objects_in_fov = []
        for _ in range(3):
            feed_frame_to_nvr(nvr)
            nvr._run()
            assert camera.is_recording
            assert nvr._stop_recorder_at is None

        motion_detector.motion_detected = False
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr._stop_recorder_at is not None

        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        fake_time.advance(1)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert not camera.is_recording


class TestNVRRunManualRecording:
    """_run tests (manual recording)."""

    def test_manual_recording_start_when_idle(self, vis, monkeypatch, caplog):
        """Start manual recording when idle."""
        nvr, camera = make_nvr(vis, camera_output_fps=5)
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # Schedule manual recording
        nvr.start_manual_recording(ManualRecording(duration=3))
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording
        assert camera.recorder.active_recording.trigger_type == TriggerTypes.MANUAL

        # Advance less than duration -> still recording
        fake_time.advance(2)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording

        # Advance beyond duration -> stops
        fake_time.advance(2)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr.stop_recorder.called_once_with(True)
        assert not camera.is_recording

    def test_manual_recording_overrides_object_event(self, vis, monkeypatch, caplog):
        """Manual overrides ongoing object event recording."""
        caplog.set_level(logging.DEBUG, logger="viseron.components.nvr.nvr")
        object_detector = MockObjectDetector(fps=5, scan_on_motion_only=False)
        nvr, camera = make_nvr(
            vis, camera_output_fps=5, object_detector=object_detector
        )
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # Trigger object event recording
        object_detector.objects_in_fov = [
            SimpleNamespace(trigger_event_recording=True, label="person")
        ]
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording
        assert camera.recorder.active_recording.trigger_type == TriggerTypes.OBJECT

        # Start manual recording while event is active
        nvr.start_manual_recording(ManualRecording(duration=2))
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert camera.recorder.active_recording.trigger_type == TriggerTypes.MANUAL
        assert camera.stop_recorder.called_once_with(True)
        assert "Event recording in progress" in caplog.text

        # End after duration
        fake_time.advance(3)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr.stop_recorder.called_once_with(True)
        assert not camera.is_recording

    def test_manual_recording_overrides_motion_event(self, vis, monkeypatch, caplog):
        """Manual overrides ongoing motion event recording."""
        caplog.set_level(logging.DEBUG, logger="viseron.components.nvr.nvr")
        motion_detector = MockMotionDetector(fps=5, trigger_event_recording=True)
        nvr, camera = make_nvr(
            vis, camera_output_fps=5, motion_detector=motion_detector
        )
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        # Trigger motion event recording
        motion_detector.motion_detected = True
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording
        assert camera.recorder.active_recording.trigger_type == TriggerTypes.MOTION

        # Start manual recording
        nvr.start_manual_recording(ManualRecording(duration=2))
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert camera.is_recording
        assert camera.recorder.active_recording.trigger_type == TriggerTypes.MANUAL
        assert camera.stop_recorder.called_once_with(True)
        assert "Event recording in progress" in caplog.text

        # Advance beyond duration -> stops
        fake_time.advance(3)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr.stop_recorder.called_once_with(True)
        assert not camera.is_recording

    def test_manual_recording_does_not_restart_each_frame(
        self, vis, monkeypatch, caplog
    ):
        """Manual recording only triggers once."""
        caplog.set_level(logging.DEBUG, logger="viseron.components.nvr.nvr")
        nvr, camera = make_nvr(vis, camera_output_fps=5)
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        nvr.start_manual_recording(ManualRecording(duration=4))
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording

        # Subsequent frames before duration end should not start again
        for _ in range(1, 3):
            fake_time.advance(1)
            feed_frame_to_nvr(nvr)
            nvr._run()
            assert camera.is_recording
            assert camera.start_recorder.call_count == 1

        # After duration exceeded, recording stops
        fake_time.advance(3)
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert nvr.stop_recorder.called_once_with(True)
        assert not camera.is_recording

    def test_manual_recording_no_duration(self, vis, monkeypatch, caplog):
        """Manual recording without duration."""
        caplog.set_level(logging.DEBUG, logger="viseron.components.nvr.nvr")
        nvr, camera = make_nvr(vis, camera_output_fps=5)
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        nvr.start_manual_recording(ManualRecording(duration=None))
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording

        # Advance time indefinitely -> recording continues
        for _ in range(1, 6):
            fake_time.advance(1)
            feed_frame_to_nvr(nvr)
            nvr._run()
            assert camera.is_recording

        nvr.stop_manual_recording()
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert "Received request to stop manual recording" in caplog.text
        assert nvr.stop_recorder.called_once_with(True)
        assert not camera.is_recording

    def test_manual_recording_no_duration_max_recording_time_exceeded(
        self, vis, monkeypatch, caplog
    ):
        """Manual recording without duration."""
        caplog.set_level(logging.DEBUG, logger="viseron.components.nvr.nvr")
        nvr, camera = make_nvr(vis, camera_output_fps=5)
        fake_time = FakeTime()
        patch_nvr_utcnow(monkeypatch, fake_time)
        configure_camera_for_recording_tests(camera, fake_time, idle_timeout=2)

        nvr.start_manual_recording(ManualRecording(duration=None))
        feed_frame_to_nvr(nvr)
        nvr._run(first_frame_log=True)
        assert camera.is_recording

        camera.recorder.max_recording_time_exceeded = True
        feed_frame_to_nvr(nvr)
        nvr._run()
        assert "Max recording time exceeded, stopping recorder" in caplog.text
        assert nvr.stop_recorder.called_once_with(True)
        assert not camera.is_recording
