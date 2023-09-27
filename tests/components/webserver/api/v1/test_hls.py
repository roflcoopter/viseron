"""Test the HLS API handler."""

import datetime
from unittest.mock import patch

from sqlalchemy import update

from viseron.components.storage.models import Recordings
from viseron.domains.camera.const import CONFIG_LOOKBACK, CONFIG_RECORDER

from tests.common import BaseTestWithRecordings, MockCamera
from tests.components.webserver.common import TestAppBaseNoAuth


class TestHlsApiHandler(TestAppBaseNoAuth, BaseTestWithRecordings):
    """Test the HLS API handler."""

    def test_get_recording_hls_playlist(self):
        """Test getting a recording HLS playlist."""
        mocked_camera = MockCamera(
            identifier="test", config={CONFIG_RECORDER: {CONFIG_LOOKBACK: 5}}
        )
        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=mocked_camera,
        ), patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler"
                "._get_session"
            ),
            return_value=self._get_db_session(),
        ):
            response = self.fetch("/api/v1/hls/test/1/index.m3u8")
        assert response.code == 200
        response_string = response.body.decode()
        assert response_string.count("#EXTINF") == 3
        assert response_string.count("#EXT-X-DISCONTINUITY") == 3
        assert response_string.count("#EXT-X-ENDLIST") == 1

    def test_get_recording_hls_ongoing(self):
        """Test getting a recording HLS playlist for a recording that has not ended."""
        recording_id = 2
        with self._get_db_session() as session:
            session.execute(
                update(Recordings)
                .values(end_time=None)
                .where(Recordings.id == recording_id)
            )
            session.commit()

        mocked_camera = MockCamera(
            identifier="test", config={CONFIG_RECORDER: {CONFIG_LOOKBACK: 5}}
        )
        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=mocked_camera,
        ), patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler"
                "._get_session"
            ),
            return_value=self._get_db_session(),
        ), patch(
            "viseron.components.webserver.api.v1.hls.utcnow",
            return_value=self._now + datetime.timedelta(seconds=36),
        ):
            response = self.fetch(f"/api/v1/hls/test/{recording_id}/index.m3u8")

        assert response.code == 200
        response_string = response.body.decode()
        assert response_string.count("#EXTINF") == 4
        assert response_string.count("#EXT-X-DISCONTINUITY") == 4
        assert response_string.count("#EXT-X-ENDLIST") == 0
