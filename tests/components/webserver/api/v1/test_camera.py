"""Tests for CameraAPIHandler manual recording endpoint."""
from __future__ import annotations

import json
from collections.abc import Callable
from unittest.mock import MagicMock, patch

from viseron.components.storage.models import TriggerTypes
from viseron.domains.camera.recorder import ManualRecording

from tests.common import MockCamera
from tests.components.webserver.common import TestAppBaseAuth


async def _fast_sleep(*_: object, **__: object) -> None:
    """Async no-op used to bypass real sleeping in wait loops."""


def _ticking_time(start: int = 0) -> Callable[[], float]:
    """Return a time.time replacement that increments on each call."""

    current = start

    def _time() -> float:
        nonlocal current
        current += 1
        return float(current)

    return _time


class TestCameraAPIHandlerManualRecording(TestAppBaseAuth):
    """Test manual recording start/stop flows."""

    def _build_camera_and_nvr(
        self, *, is_recording: bool, connected: bool = True
    ) -> tuple[MockCamera, MagicMock]:
        camera = MockCamera(identifier="test")
        camera.is_recording = is_recording
        camera.connected = connected
        camera.recorder.active_recording = (
            MagicMock(trigger_type=TriggerTypes.MANUAL) if is_recording else None
        )

        nvr = MagicMock()
        nvr.camera = camera
        return camera, nvr

    def test_manual_recording_start_success(self):
        """Start manual recording succeeds when NVR flips recording state."""

        camera, nvr = self._build_camera_and_nvr(is_recording=False)

        def start_manual_recording(_: ManualRecording) -> None:
            nvr.camera.is_recording = True
            nvr.camera.recorder.active_recording = MagicMock(
                trigger_type=TriggerTypes.MANUAL
            )

        nvr.start_manual_recording = MagicMock(side_effect=start_manual_recording)

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=nvr), patch(
            "viseron.components.webserver.api.v1.camera.asyncio.sleep", new=_fast_sleep
        ), patch(
            "viseron.components.webserver.api.v1.camera.time.time", new=_ticking_time()
        ):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/manual_recording",
                method="POST",
                body=json.dumps({"action": "start", "duration": 5}),
            )

        assert response.code == 200
        assert json.loads(response.body) == {"success": True}
        assert nvr.start_manual_recording.call_count == 1
        assert nvr.camera.is_recording is True
        assert nvr.camera.recorder.active_recording.trigger_type == TriggerTypes.MANUAL

    def test_manual_recording_start_timeout(self):
        """Start manual recording returns 500 when recording never becomes active."""

        camera, nvr = self._build_camera_and_nvr(is_recording=False)
        nvr.start_manual_recording = MagicMock()

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=nvr), patch(
            "viseron.components.webserver.api.v1.camera.asyncio.sleep", new=_fast_sleep
        ), patch(
            "viseron.components.webserver.api.v1.camera.time.time", new=_ticking_time()
        ):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/manual_recording",
                method="POST",
                body=json.dumps({"action": "start"}),
            )

        assert response.code == 500
        assert json.loads(response.body) == {
            "error": "Failed to start manual recording",
            "status": 500,
        }
        assert nvr.start_manual_recording.call_count == 1
        assert nvr.camera.is_recording is False

    def test_manual_recording_stop_success(self):
        """Stop manual recording succeeds when NVR clears recording state."""

        camera, nvr = self._build_camera_and_nvr(is_recording=True)

        def stop_manual_recording() -> None:
            nvr.camera.is_recording = False
            nvr.camera.recorder.active_recording = None

        nvr.stop_manual_recording = MagicMock(side_effect=stop_manual_recording)

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=nvr), patch(
            "viseron.components.webserver.api.v1.camera.asyncio.sleep", new=_fast_sleep
        ), patch(
            "viseron.components.webserver.api.v1.camera.time.time", new=_ticking_time()
        ):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/manual_recording",
                method="POST",
                body=json.dumps({"action": "stop"}),
            )

        assert response.code == 200
        assert json.loads(response.body) == {"success": True}
        assert nvr.stop_manual_recording.call_count == 1
        assert nvr.camera.is_recording is False
        assert nvr.camera.recorder.active_recording is None

    def test_manual_recording_stop_timeout(self):
        """Stop manual recording returns 500 when recording never stops."""

        camera, nvr = self._build_camera_and_nvr(is_recording=True)
        nvr.stop_manual_recording = MagicMock()

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=nvr), patch(
            "viseron.components.webserver.api.v1.camera.asyncio.sleep", new=_fast_sleep
        ), patch(
            "viseron.components.webserver.api.v1.camera.time.time", new=_ticking_time()
        ):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/manual_recording",
                method="POST",
                body=json.dumps({"action": "stop"}),
            )

        assert response.code == 500
        assert json.loads(response.body) == {
            "error": "Failed to stop manual recording",
            "status": 500,
        }
        assert nvr.stop_manual_recording.call_count == 1
        assert nvr.camera.is_recording is True

    def test_manual_recording_camera_not_found(self):
        """Returns 404 when camera is missing."""

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=None,
        ):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/manual_recording",
                method="POST",
                body=json.dumps({"action": "start"}),
            )

        assert response.code == 404
        assert json.loads(response.body) == {
            "error": "Camera test not found",
            "status": 404,
        }

    def test_manual_recording_camera_off(self):
        """Returns 400 when camera is off."""
        camera, nvr = self._build_camera_and_nvr(is_recording=False, connected=False)

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=nvr):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/manual_recording",
                method="POST",
                body=json.dumps({"action": "start"}),
            )

        assert response.code == 400
        assert json.loads(response.body) == {
            "error": "Camera is off or disconnected",
            "status": 400,
        }
        assert nvr.camera.is_recording is False

    def test_manual_recording_nvr_not_found(self):
        """Returns 404 when NVR domain is missing."""

        camera = MockCamera(identifier="test")

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=None):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/manual_recording",
                method="POST",
                body=json.dumps({"action": "start"}),
            )

        assert response.code == 404
        assert json.loads(response.body) == {
            "error": "NVR for camera test not found",
            "status": 404,
        }

    def test_manual_recording_nvr_is_idle(self):
        """Returns 400 when camera is off."""
        camera, nvr = self._build_camera_and_nvr(is_recording=False)
        nvr.operation_state = "idle"

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=nvr):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/manual_recording",
                method="POST",
                body=json.dumps({"action": "start"}),
            )

        assert response.code == 400
        assert json.loads(response.body) == {
            "error": "NVR is idle",
            "status": 400,
        }
        assert nvr.camera.is_recording is False

    def test_manual_recording_invalid_body(self):
        """Invalid action schema returns 400 without hitting handler logic."""

        response = self.fetch_with_auth(
            "/api/v1/camera/test/manual_recording",
            method="POST",
            body=json.dumps({"action": "invalid"}),
        )

        assert response.code == 400
        body = json.loads(response.body)
        assert body["status"] == 400
        assert "Invalid body" in body["error"]

    def test_start_camera_success(self):
        """Start camera triggers start_camera when off."""
        camera = MockCamera(identifier="test")
        camera.is_on = False

        def start_camera() -> None:
            camera.is_on = True

        camera.start_camera = MagicMock(side_effect=start_camera)

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=MagicMock()):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/start",
                method="POST",
                body="",
            )

        assert response.code == 200
        assert json.loads(response.body) == {"success": True}
        assert camera.start_camera.call_count == 1
        assert camera.is_on is True

    def test_start_camera_already_on(self):
        """Start camera is a no-op when already on."""
        camera = MockCamera(identifier="test")
        camera.is_on = True
        camera.start_camera = MagicMock()

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=MagicMock()):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/start",
                method="POST",
                body="",
            )

        assert response.code == 200
        assert json.loads(response.body) == {"success": True}
        camera.start_camera.assert_not_called()

    def test_start_camera_not_found(self):
        """Start camera returns 404 when camera missing."""
        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=None,
        ):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/start",
                method="POST",
                body="",
            )

        assert response.code == 404
        assert json.loads(response.body) == {
            "error": "Camera test not found",
            "status": 404,
        }

    def test_start_camera_nvr_not_found(self):
        """Start camera returns 404 when NVR missing."""
        camera = MockCamera(identifier="test")
        camera.is_on = False

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=None):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/start",
                method="POST",
                body="",
            )

        assert response.code == 404
        assert json.loads(response.body) == {
            "error": "NVR for camera test not found",
            "status": 404,
        }

    def test_stop_camera_success(self):
        """Stop camera triggers stop_camera when on."""
        camera = MockCamera(identifier="test")
        camera.is_on = True

        def stop_camera() -> None:
            camera.is_on = False

        camera.stop_camera = MagicMock(side_effect=stop_camera)

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=MagicMock()):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/stop",
                method="POST",
                body="",
            )

        assert response.code == 200
        assert json.loads(response.body) == {"success": True}
        assert camera.stop_camera.call_count == 1
        assert camera.is_on is False

    def test_stop_camera_already_off(self):
        """Stop camera is a no-op when already off."""
        camera = MockCamera(identifier="test")
        camera.is_on = False
        camera.stop_camera = MagicMock()

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=MagicMock()):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/stop",
                method="POST",
                body="",
            )

        assert response.code == 200
        assert json.loads(response.body) == {"success": True}
        camera.stop_camera.assert_not_called()

    def test_stop_camera_not_found(self):
        """Stop camera returns 404 when camera missing."""
        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=None,
        ):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/stop",
                method="POST",
                body="",
            )

        assert response.code == 404
        assert json.loads(response.body) == {
            "error": "Camera test not found",
            "status": 404,
        }

    def test_stop_camera_nvr_not_found(self):
        """Stop camera returns 404 when NVR missing."""
        camera = MockCamera(identifier="test")
        camera.is_on = True

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=camera,
        ), patch.object(self.vis, "get_registered_domain", return_value=None):
            response = self.fetch_with_auth(
                "/api/v1/camera/test/stop",
                method="POST",
                body="",
            )

        assert response.code == 404
        assert json.loads(response.body) == {
            "error": "NVR for camera test not found",
            "status": 404,
        }
