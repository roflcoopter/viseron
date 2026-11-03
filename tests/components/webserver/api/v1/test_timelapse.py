"""Test the Timelapse API handler."""

from __future__ import annotations

import datetime
import json
import os
import tempfile
from concurrent.futures import Future
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from sqlalchemy import insert

from viseron.components.storage.const import (
    TIER_CATEGORY_TIMELAPSE,
    TIER_SUBCATEGORY_TIMELAPSE,
    TIMELAPSE_SEGMENT_ENCODER,
)
from viseron.components.storage.models import Files
from viseron.components.storage.timelapse_segments import (
    SegmentRequest,
    TimelapseSegmentBusyError,
    TimelapseSegmentError,
)
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import Role, User

from tests.common import MockCamera
from tests.components.webserver.common import TestAppBaseNoAuth

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker
    from tornado.httpclient import HTTPResponse

EPOCH = 1_700_000_000


def _user(assigned_cameras: list[str]) -> User:
    return User(
        name="test",
        username="test",
        password="test",
        role=Role.READ,
        assigned_cameras=assigned_cameras,
    )


class TestTimelapseApiHandler(TestAppBaseNoAuth):
    """Test the Timelapse API handler."""

    @pytest.fixture(autouse=True)
    def prepare_and_mock(self, get_db_session: sessionmaker[Session]):
        """Insert timelapse frames and register cameras."""
        with get_db_session() as session:
            # 2023-11-14 22:13:20, 23:13:20 and 2023-11-15 00:13:20 UTC
            for file_key, offset in enumerate((0, 3600, 7200), start=1):
                timestamp = datetime.datetime.fromtimestamp(
                    EPOCH + offset, tz=datetime.timezone.utc
                )
                filename = f"{EPOCH + offset}.jpg"
                session.execute(
                    insert(Files).values(
                        file_key=file_key,
                        tier_id=0,
                        tier_path="/segments/",
                        camera_identifier="test",
                        category=TIER_CATEGORY_TIMELAPSE,
                        subcategory=TIER_SUBCATEGORY_TIMELAPSE,
                        path=f"/segments/timelapse/test/{filename}",
                        directory="/segments/timelapse/test",
                        filename=filename,
                        size=10,
                        orig_ctime=timestamp,
                        duration=None,
                    )
                )
            session.commit()

        with patch(
            (
                "viseron.components.webserver.request_handler."
                "ViseronRequestHandler._get_session"
            ),
            return_value=get_db_session(),
        ):
            yield

    def setUp(self) -> None:
        """Register cameras with and without timelapse enabled."""
        super().setUp()
        MockCamera(
            vis=self.vis, identifier="test", timelapse_folder="/segments/timelapse/test"
        )
        MockCamera(
            vis=self.vis, identifier="empty", timelapse_folder="/segments/timelapse/e"
        )
        MockCamera(vis=self.vis, identifier="no_timelapse", timelapse_folder=None)

    def _fetch_as(self, path: str, user: User | None) -> HTTPResponse:
        with patch.object(
            BaseAPIHandler, "current_user", new_callable=PropertyMock
        ) as current_user:
            current_user.return_value = user
            return self.fetch(path)

    def test_get_summary(self) -> None:
        """Test that only cameras with timelapse enabled are summarized."""
        response = self.fetch("/api/v1/timelapse")

        assert response.code == 200
        assert json.loads(response.body) == {
            "cameras": {
                "test": {
                    "camera_identifier": "test",
                    "count": 3,
                    "first_timestamp": EPOCH,
                    "last_timestamp": EPOCH + 7200,
                    "latest_frame": {
                        "file_key": 3,
                        "timestamp": EPOCH + 7200,
                        "path": "/file/test/3",
                    },
                },
                "empty": {
                    "camera_identifier": "empty",
                    "count": 0,
                    "first_timestamp": None,
                    "last_timestamp": None,
                    "latest_frame": None,
                },
            }
        }

    def test_get_summary_skips_unassigned_cameras(self) -> None:
        """Test that cameras the user is not assigned to are left out."""
        response = self._fetch_as("/api/v1/timelapse", _user(["empty"]))

        assert response.code == 200
        assert list(json.loads(response.body)["cameras"]) == ["empty"]

    def test_get_frames(self) -> None:
        """Test getting the frames in a time range."""
        response = self.fetch(
            f"/api/v1/timelapse/test?start={EPOCH}&end={EPOCH + 3600}"
        )

        assert response.code == 200
        assert json.loads(response.body) == {
            "camera_identifier": "test",
            "start": EPOCH,
            "end": EPOCH + 3600,
            "step": None,
            "total": 2,
            "stream": None,
            "frames": [
                {
                    "file_key": 1,
                    "timestamp": EPOCH,
                    "path": "/file/test/1",
                },
                {
                    "file_key": 2,
                    "timestamp": EPOCH + 3600,
                    "path": "/file/test/2",
                },
            ],
        }

    def test_get_frames_downsampled(self) -> None:
        """Test that max_frames limits the number of returned frames."""
        response = self.fetch(
            f"/api/v1/timelapse/test?start={EPOCH}&end={EPOCH + 7200}&max_frames=2"
        )

        assert response.code == 200
        body = json.loads(response.body)
        assert body["total"] == 3
        assert body["step"] == 3600
        assert [frame["file_key"] for frame in body["frames"]] == [1, 2]

    def test_get_frames_bad_arguments(self) -> None:
        """Test that invalid arguments are rejected."""
        for query in (
            f"start={EPOCH}",
            f"start={EPOCH}&end={EPOCH}",
            f"start={EPOCH}&end={EPOCH - 1}",
            f"start={EPOCH}&end={EPOCH + 1}&max_frames=0",
            f"start={EPOCH}&end={EPOCH + 1}&max_frames=20001",
            "start=abc&end=def",
            f"start=nan&end={EPOCH}",
            f"start={EPOCH}&end=nan",
            f"start={EPOCH}&end=inf",
            f"start=-1&end={EPOCH}",
            f"start={EPOCH}&end=1e300",
        ):
            response = self.fetch(f"/api/v1/timelapse/test?{query}")

            assert response.code == 400, query

    def _assert_camera_not_found(
        self, camera_identifier: str, user: User | None
    ) -> None:
        for path in (
            f"?start={EPOCH}&end={EPOCH + 1}",
            "/dates_of_interest",
            "/segment?keys=1&start_frame=0&width=2&height=2",
        ):
            response = self._fetch_as(
                f"/api/v1/timelapse/{camera_identifier}{path}", user
            )

            assert response.code == 404, path

    def test_unknown_camera(self) -> None:
        """Test that an unknown camera returns 404."""
        self._assert_camera_not_found("unknown", None)

    def test_timelapse_disabled(self) -> None:
        """Test that a camera without timelapse enabled returns 404."""
        self._assert_camera_not_found("no_timelapse", None)

    def test_unassigned_camera(self) -> None:
        """Test that a camera the user is not assigned to returns 404."""
        self._assert_camera_not_found("test", _user(["empty"]))

    def _get_dates_of_interest(
        self, utc_offset_minutes: int, expected: dict[str, dict[str, int]]
    ) -> None:
        response = self.fetch(
            "/api/v1/timelapse/test/dates_of_interest",
            headers={"X-Client-UTC-Offset": str(utc_offset_minutes)},
        )

        assert response.code == 200
        assert json.loads(response.body) == {"dates_of_interest": expected}

    def test_get_dates_of_interest(self) -> None:
        """Test that frames are counted per UTC day."""
        self._get_dates_of_interest(
            0, {"2023-11-14": {"frames": 2}, "2023-11-15": {"frames": 1}}
        )

    def test_get_dates_of_interest_utc_offset(self) -> None:
        """Test that frames are counted per day in the client's timezone."""
        self._get_dates_of_interest(
            60, {"2023-11-14": {"frames": 1}, "2023-11-15": {"frames": 2}}
        )

    def test_get_frames_stream(self) -> None:
        """Test that the stream parameters are returned when a frame is readable."""
        with patch(
            "viseron.components.webserver.api.v1.timelapse.stream_size",
            return_value=(1280, 720),
        ) as size:
            response = self.fetch(
                f"/api/v1/timelapse/test?start={EPOCH}&end={EPOCH + 3600}"
            )

        assert response.code == 200
        assert json.loads(response.body)["stream"] == {
            "fps": 15,
            "segment_frames": 60,
            "width": 1280,
            "height": 720,
        }
        assert size.call_args.args[3] == 1280

    def _fetch_segment(
        self, future: Future[str] | None, side_effect: Exception | None = None
    ) -> tuple[HTTPResponse, MagicMock]:
        with patch.object(
            self.vis.data[TIMELAPSE_SEGMENT_ENCODER],
            "get",
            return_value=future,
            side_effect=side_effect,
        ) as get:
            response = self.fetch(
                "/api/v1/timelapse/test/segment"
                "?keys=1,1a&start_frame=60&width=1280&height=720"
            )
        return response, get

    def test_get_segment(self) -> None:
        """Test that a segment is encoded from the frames in the URL."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "segment.ts")
            with open(path, "wb") as file:
                file.write(b"segment")
            future: Future[str] = Future()
            future.set_result(path)

            response, get = self._fetch_segment(future)

        assert response.code == 200
        assert response.body == b"segment"
        assert response.headers["Content-Type"] == "video/mp2t"
        assert "immutable" in response.headers["Cache-Control"]
        assert get.call_args.args[0] == SegmentRequest(
            camera_identifier="test",
            file_keys=(1, 26),
            start_frame=60,
            width=1280,
            height=720,
        )

    def test_get_segment_encode_error(self) -> None:
        """Test that a failed encode returns 500."""
        future: Future[str] = Future()
        future.set_exception(TimelapseSegmentError("boom"))

        response, _get = self._fetch_segment(future)

        assert response.code == 500

    def test_get_segment_encoder_busy(self) -> None:
        """Test that a segment is rejected while too many encodes are pending."""
        response, _get = self._fetch_segment(None, TimelapseSegmentBusyError())

        assert response.code == 503
        assert response.headers["Retry-After"] == "5"

    def test_get_segment_bad_arguments(self) -> None:
        """Test that invalid segment arguments are rejected."""
        valid = "start_frame=0&width=64&height=48"
        for query in (
            f"keys=&{valid}",
            f"keys=xyz&{valid}",
            f"keys=1,,2&{valid}",
            f"keys=1234567890abcdef&{valid}",
            f"keys={','.join(['1'] * 61)}&{valid}",
            "keys=1&start_frame=-1&width=64&height=48",
            "keys=1&start_frame=0&width=63&height=48",
            "keys=1&start_frame=0&width=0&height=48",
            "keys=1&start_frame=0&width=64&height=5000",
        ):
            response = self.fetch(f"/api/v1/timelapse/test/segment?{query}")

            assert response.code == 400, query
