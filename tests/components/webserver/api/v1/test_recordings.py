"""Test the Recordings API handler."""
from __future__ import annotations

import datetime
import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm.session import Session, sessionmaker

from tests.common import BaseTestWithRecordings, MockCamera
from tests.components.webserver.common import TestAppBaseNoAuth


class TestRecordingsApiHandler(TestAppBaseNoAuth, BaseTestWithRecordings):
    """Test the Recordings API handler."""

    @pytest.fixture(scope="function", autouse=True)
    def prepare_and_mock(self, get_db_session: sessionmaker[Session]):
        """Prepare the database with recordings and setup mocks."""
        mock_recordings = {
            "2024-06-22": {
                "1": {
                    "id": 1,
                    "camera_identifier": "test",
                    "path": "/recordings/test/2024-06-22/recording_1.mp4",
                    "start_time": datetime.datetime(
                        2024, 6, 22, 1, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                    "end_time": datetime.datetime(
                        2024, 6, 22, 1, 1, 0, tzinfo=datetime.timezone.utc
                    ),
                },
                "2": {
                    "id": 2,
                    "camera_identifier": "test",
                    "path": "/recordings/test/2024-06-22/recording_2.mp4",
                    "start_time": datetime.datetime(
                        2024, 6, 22, 3, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                    "end_time": datetime.datetime(
                        2024, 6, 22, 3, 1, 0, tzinfo=datetime.timezone.utc
                    ),
                },
            },
            "2024-06-23": {
                "3": {
                    "id": 3,
                    "camera_identifier": "test",
                    "path": "/recordings/test/2024-06-23/recording_3.mp4",
                    "start_time": datetime.datetime(
                        2024, 6, 23, 1, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                    "end_time": datetime.datetime(
                        2024, 6, 23, 1, 1, 0, tzinfo=datetime.timezone.utc
                    ),
                }
            },
            "2024-06-24": {
                "4": {
                    "id": 4,
                    "camera_identifier": "test",
                    "path": "/recordings/test/2024-06-24/recording_4.mp4",
                    "start_time": datetime.datetime(
                        2024, 6, 24, 1, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                    "end_time": datetime.datetime(
                        2024, 6, 24, 1, 1, 0, tzinfo=datetime.timezone.utc
                    ),
                }
            },
        }

        # Create a different set of recordings for test2 camera
        mock_recordings_test2 = {
            "2024-06-22": {
                "5": {
                    "id": 5,
                    "camera_identifier": "test2",
                    "path": "/recordings/test2/2024-06-22/recording_5.mp4",
                    "start_time": datetime.datetime(
                        2024, 6, 22, 1, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                    "end_time": datetime.datetime(
                        2024, 6, 22, 1, 1, 0, tzinfo=datetime.timezone.utc
                    ),
                }
            }
        }

        mock_camera = MockCamera(identifier="test")
        mock_camera.recorder = MagicMock()
        mock_camera.recorder.get_recordings.return_value = mock_recordings
        mock_camera.recorder.get_latest_recording.return_value = mock_recordings[
            "2024-06-24"
        ]["4"]
        mock_camera.recorder.get_latest_recording_daily.return_value = {
            "2024-06-24": mock_recordings["2024-06-24"]["4"]
        }
        mock_camera.recorder.delete_recording.return_value = True

        mock_camera2 = MockCamera(identifier="test2")
        mock_camera2.recorder = MagicMock()
        mock_camera2.recorder.get_recordings.return_value = mock_recordings_test2
        mock_camera2.recorder.get_latest_recording.return_value = mock_recordings_test2[
            "2024-06-22"
        ]["5"]
        mock_camera2.recorder.get_latest_recording_daily.return_value = {
            "2024-06-22": mock_recordings_test2["2024-06-22"]["5"]
        }
        mock_camera2.recorder.delete_recording.return_value = True

        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=mock_camera,
        ), patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_cameras"
            ),
            return_value={"test": mock_camera, "test2": mock_camera2},
        ), patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler"
                "._get_session"
            ),
            return_value=get_db_session(),
        ):
            yield

    def test_get_recordings(self):
        """Test getting all recordings."""
        response = self.fetch("/api/v1/recordings")
        assert response.code == 200
        body = json.loads(response.body)

        assert "test" in body
        assert "test2" in body

        # Verify test camera recordings
        test_recordings = body["test"]
        assert "2024-06-22" in test_recordings
        assert "2024-06-23" in test_recordings
        assert "2024-06-24" in test_recordings
        assert len(test_recordings["2024-06-22"]) == 2
        assert len(test_recordings["2024-06-23"]) == 1
        assert len(test_recordings["2024-06-24"]) == 1

        # Verify specific recording
        assert (
            test_recordings["2024-06-22"]["1"]["path"]
            == "/recordings/test/2024-06-22/recording_1.mp4"
        )
        assert (
            test_recordings["2024-06-22"]["1"]["start_time"]
            == "2024-06-22T01:00:00+00:00"
        )
        assert (
            test_recordings["2024-06-22"]["1"]["end_time"]
            == "2024-06-22T01:01:00+00:00"
        )

        # Verify test2 camera recordings
        test2_recordings = body["test2"]
        assert "2024-06-22" in test2_recordings
        assert len(test2_recordings["2024-06-22"]) == 1
        assert (
            test2_recordings["2024-06-22"]["5"]["path"]
            == "/recordings/test2/2024-06-22/recording_5.mp4"
        )

    def test_get_recordings_latest(self):
        """Test getting latest recording."""
        response = self.fetch("/api/v1/recordings?latest")
        assert response.code == 200
        body = json.loads(response.body)

        assert "test" in body
        assert "test2" in body
        assert body["test"]["id"] == 4
        assert body["test"]["start_time"] == "2024-06-24T01:00:00+00:00"
        assert body["test2"]["id"] == 5
        assert body["test2"]["start_time"] == "2024-06-22T01:00:00+00:00"

    def test_get_recordings_latest_daily(self):
        """Test getting latest daily recording."""
        response = self.fetch("/api/v1/recordings?latest&daily")
        assert response.code == 200
        body = json.loads(response.body)

        assert "test" in body
        assert "test2" in body
        assert "2024-06-24" in body["test"]
        assert body["test"]["2024-06-24"]["id"] == 4
        assert "2024-06-22" in body["test2"]
        assert body["test2"]["2024-06-22"]["id"] == 5

    def test_get_recordings_camera(self):
        """Test getting recordings for specific camera."""
        response = self.fetch("/api/v1/recordings/test")
        assert response.code == 200
        body = json.loads(response.body)

        assert "2024-06-22" in body
        assert "2024-06-23" in body
        assert "2024-06-24" in body
        assert len(body["2024-06-22"]) == 2
        assert len(body["2024-06-23"]) == 1
        assert len(body["2024-06-24"]) == 1

    def test_get_recordings_camera_date(self):
        """Test getting recordings for specific camera and date."""
        response = self.fetch("/api/v1/recordings/test/2024-06-22")
        assert response.code == 200
        body = json.loads(response.body)

        assert "2024-06-22" in body
        assert len(body["2024-06-22"]) == 2
        assert body["2024-06-22"]["1"]["start_time"] == "2024-06-22T01:00:00+00:00"
        assert body["2024-06-22"]["2"]["start_time"] == "2024-06-22T03:00:00+00:00"

    def test_get_recordings_invalid_camera(self):
        """Test getting recordings for invalid camera."""
        with patch(
            "viseron.components.webserver.request_handler.ViseronRequestHandler"
            "._get_camera",
            return_value=None,
        ):
            response = self.fetch("/api/v1/recordings/invalid")
            assert response.code == 404

    def test_delete_recording(self):
        """Test deleting a specific recording."""
        response = self.fetch(
            "/api/v1/recordings/test/1",
            method="DELETE",
        )
        assert response.code == 200

    def test_delete_recordings_date(self):
        """Test deleting all recordings for a specific date."""
        response = self.fetch(
            "/api/v1/recordings/test/2024-06-22",
            method="DELETE",
        )
        assert response.code == 200

    def test_delete_recordings_camera(self):
        """Test deleting all recordings for a specific camera."""
        response = self.fetch(
            "/api/v1/recordings/test",
            method="DELETE",
        )
        assert response.code == 200

    def test_delete_recording_invalid_camera(self):
        """Test deleting recording for invalid camera."""
        with patch(
            "viseron.components.webserver.request_handler.ViseronRequestHandler"
            "._get_camera",
            return_value=None,
        ):
            response = self.fetch(
                "/api/v1/recordings/invalid/1",
                method="DELETE",
            )
            assert response.code == 404

    def test_delete_recording_failure(self):
        """Test deleting recording when deletion fails."""
        mock_camera = MockCamera(identifier="test")
        mock_camera.recorder = MagicMock()
        mock_camera.recorder.delete_recording.return_value = False

        with patch(
            "viseron.components.webserver.request_handler.ViseronRequestHandler"
            "._get_camera",
            return_value=mock_camera,
        ):
            response = self.fetch(
                "/api/v1/recordings/test/1",
                method="DELETE",
            )
            assert response.code == 500
