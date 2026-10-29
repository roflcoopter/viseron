"""Test the Cameras API handler."""

from __future__ import annotations

import json
from unittest.mock import PropertyMock, patch

from viseron.components.storage.orphaned_cameras import (
    OrphanedCamera,
    OrphanedCameraError,
    OrphanedCameraUnavailableError,
)
from viseron.components.webserver.auth import Role, User

from tests.components.webserver.common import TestAppBaseAuth, TestAppBaseNoAuth

ORPHANED_CAMERA = OrphanedCamera(
    camera_identifier="camera_3",
    file_count=2,
    size_bytes=2560,
    database_rows=1,
    directories=["/segments/camera_3"],
)


class TestCamerasApiHandlerNoAuth(TestAppBaseNoAuth):
    """Test the orphaned camera endpoints without auth."""

    def test_get_orphaned_cameras(self):
        """Test listing orphaned cameras."""
        with patch(
            "viseron.components.webserver.api.v1.cameras.get_orphaned_cameras",
            return_value=[ORPHANED_CAMERA],
        ):
            response = self.fetch("/api/v1/cameras/orphaned")
        assert response.code == 200
        assert json.loads(response.body) == {
            "cameras": [
                {
                    "camera_identifier": "camera_3",
                    "file_count": 2,
                    "size_bytes": 2560,
                    "database_rows": 1,
                    "directories": ["/segments/camera_3"],
                }
            ]
        }

    def test_get_orphaned_cameras_safe_mode(self):
        """Test that an unreadable config is reported as unavailable."""
        with patch(
            "viseron.components.webserver.api.v1.cameras.get_orphaned_cameras",
            side_effect=OrphanedCameraUnavailableError("safe mode"),
        ):
            response = self.fetch("/api/v1/cameras/orphaned")
        assert response.code == 503

    def test_delete_orphaned_camera(self):
        """Test deleting an orphaned camera."""
        with patch(
            "viseron.components.webserver.api.v1.cameras.delete_orphaned_camera",
            return_value=ORPHANED_CAMERA,
        ) as mock_delete:
            response = self.fetch("/api/v1/cameras/orphaned/camera_3", method="DELETE")
        assert response.code == 200
        assert json.loads(response.body)["camera_identifier"] == "camera_3"
        assert mock_delete.call_args[0][2] == "camera_3"

    def test_delete_orphaned_camera_still_configured(self):
        """Test that deleting a configured camera is a client error."""
        with patch(
            "viseron.components.webserver.api.v1.cameras.delete_orphaned_camera",
            side_effect=OrphanedCameraError("still configured"),
        ):
            response = self.fetch("/api/v1/cameras/orphaned/camera_1", method="DELETE")
        assert response.code == 400

    def test_delete_orphaned_camera_invalid_identifier(self):
        """Test that an identifier that is not a slug does not match the route."""
        with patch(
            "viseron.components.webserver.api.v1.cameras.delete_orphaned_camera"
        ) as mock_delete:
            response = self.fetch("/api/v1/cameras/orphaned/camera-3", method="DELETE")
        assert response.code == 404
        mock_delete.assert_not_called()


class TestCamerasApiHandlerAuth(TestAppBaseAuth):
    """Test that the orphaned camera endpoints require an admin."""

    def test_get_orphaned_cameras_non_admin(self):
        """Test listing orphaned cameras as a non-admin."""
        with (
            patch(
                "viseron.components.webserver.request_handler.ViseronRequestHandler.current_user",  # pylint: disable=line-too-long
                new_callable=PropertyMock,
                return_value=User(
                    name="Test",
                    username="test",
                    password="test",
                    role=Role.READ,
                ),
            ),
            patch(
                "viseron.components.webserver.request_handler.ViseronRequestHandler.validate_access_token",  # pylint: disable=line-too-long
                return_value=True,
            ),
        ):
            response = self.fetch_with_auth("/api/v1/cameras/orphaned")
        assert response.code == 403

    def test_delete_orphaned_camera_non_admin(self):
        """Test deleting an orphaned camera as a non-admin."""
        with (
            patch(
                "viseron.components.webserver.request_handler.ViseronRequestHandler.current_user",  # pylint: disable=line-too-long
                new_callable=PropertyMock,
                return_value=User(
                    name="Test",
                    username="test",
                    password="test",
                    role=Role.READ,
                ),
            ),
            patch(
                "viseron.components.webserver.request_handler.ViseronRequestHandler.validate_access_token",  # pylint: disable=line-too-long
                return_value=True,
            ),
            patch(
                "viseron.components.webserver.api.v1.cameras.delete_orphaned_camera"
            ) as mock_delete,
        ):
            response = self.fetch_with_auth(
                "/api/v1/cameras/orphaned/camera_3", method="DELETE"
            )
        assert response.code == 403
        mock_delete.assert_not_called()
