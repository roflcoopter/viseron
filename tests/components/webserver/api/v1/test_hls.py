"""Test the HLS API handler."""
from __future__ import annotations

import datetime
import json
from unittest.mock import patch

from sqlalchemy import delete, insert, update

from viseron.components.storage.models import Files, Recordings
from viseron.components.webserver.api.v1.hls import count_files_removed
from viseron.domains.camera.const import CONFIG_LOOKBACK, CONFIG_RECORDER
from viseron.domains.camera.fragmenter import Fragment
from viseron.helpers import utcnow

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
        ), patch(
            "viseron.components.webserver.api.v1.hls._get_init_file",
            return_value="/test/init.mp4",
        ):
            response = self.fetch("/api/v1/hls/test/1/index.m3u8")
        assert response.code == 200
        response_string = response.body.decode()
        assert response_string.count("#EXTINF") == 3
        assert response_string.count("#EXT-X-DISCONTINUITY") == 3
        assert response_string.count("#EXT-X-ENDLIST") == 1

    def test_get_recording_hls_playlist_gap_segments(self):
        """Test getting a recording HLS playlist with gap in segments."""
        with self._get_db_session() as session:
            session.execute(delete(Files).where(Files.id.in_([15, 17, 19, 21])))
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
            "viseron.components.webserver.api.v1.hls._get_init_file",
            return_value="/test/init.mp4",
        ), patch(
            "viseron.components.storage.queries.utcnow",
            return_value=self._now + datetime.timedelta(seconds=3600),
        ):
            response = self.fetch(
                "/api/v1/hls/test/index.m3u8?start_timestamp="
                f"{int(self._now.timestamp())}"
            )
        assert response.code == 200
        response_string = response.body.decode()
        assert response_string.count("#EXTINF") == 11
        assert response_string.count("#EXT-X-DISCONTINUITY") == 11
        assert response_string.count("#EXT-X-GAP") == 1

    def test_get_recording_hls_ongoing(self):
        """Test getting a recording HLS playlist for a recording that has not ended."""
        recording_id = 3
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
            "viseron.components.webserver.api.v1.hls._get_init_file",
            return_value="/test/init.mp4",
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

    def test_get_available_timespans(self):
        """Test getting available HLS timespans."""
        mocked_camera = MockCamera(
            identifier="test", config={CONFIG_RECORDER: {CONFIG_LOOKBACK: 5}}
        )

        # Insert some files in the future to mimic a gap in the timespans
        with self._get_db_session() as session:
            for i in range(5):
                timestamp = (
                    self._now
                    + datetime.timedelta(seconds=5 * i)
                    + datetime.timedelta(hours=5)
                )
                filename = f"{int(timestamp.timestamp())}.m4s"
                session.execute(
                    insert(Files).values(
                        tier_id=0,
                        tier_path="/test/",
                        camera_identifier="test",
                        category="recorder",
                        subcategory="segments",
                        path=f"/test/{filename}",
                        directory="test",
                        filename=filename,
                        size=10,
                        orig_ctime=timestamp,
                        duration=5,
                        created_at=timestamp,
                    )
                )
            session.commit()

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
            time_from = 0
            time_to = int((self._now + datetime.timedelta(days=365)).timestamp())
            response = self.fetch(
                f"/api/v1/hls/test/available_timespans"
                f"?time_from={time_from}&time_to={time_to}"
            )
        assert response.code == 200
        assert len(json.loads(response.body)["timespans"]) == 2


def test_count_files_removed_no_files_removed():
    """Test count_files_removed with no files removed."""
    prev_list = [
        Fragment("file1", "file1", 1, utcnow()),
        Fragment("file2", "file2", 1, utcnow()),
        Fragment("file3", "file3", 1, utcnow()),
    ]
    curr_list = [
        Fragment("file1", "file1", 1, utcnow()),
        Fragment("file2", "file2", 1, utcnow()),
        Fragment("file3", "file3", 1, utcnow()),
    ]
    assert count_files_removed(prev_list, curr_list) == 0


def test_count_files_removed_one_file_removed():
    """Test count_files_removed with one file removed."""
    prev_list = [
        Fragment("file1", "file1", 1, utcnow()),
        Fragment("file2", "file2", 1, utcnow()),
        Fragment("file3", "file3", 1, utcnow()),
    ]
    curr_list = [
        Fragment("file2", "file2", 1, utcnow()),
        Fragment("file3", "file3", 1, utcnow()),
    ]
    assert count_files_removed(prev_list, curr_list) == 1


def test_count_files_removed_all_files_removed():
    """Test count_files_removed with all files removed."""
    prev_list = [
        Fragment("file1", "file1", 1, utcnow()),
        Fragment("file2", "file2", 1, utcnow()),
        Fragment("file3", "file3", 1, utcnow()),
    ]
    curr_list: list[Fragment] = []
    assert count_files_removed(prev_list, curr_list) == 3


def test_count_files_removed_empty_previous_list():
    """Test count_files_removed with an empty previous list."""
    prev_list: list[Fragment] = []
    curr_list = [
        Fragment("file1", "file1", 1, utcnow()),
        Fragment("file2", "file2", 1, utcnow()),
        Fragment("file3", "file3", 1, utcnow()),
    ]
    assert count_files_removed(prev_list, curr_list) == 0


def test_count_files_removed_all_files_changed():
    """Test count_files_removed with all files changed."""
    prev_list = [
        Fragment("file1", "file1", 1, utcnow()),
        Fragment("file2", "file2", 1, utcnow()),
        Fragment("file3", "file3", 1, utcnow()),
    ]
    curr_list = [
        Fragment("file4", "file4", 1, utcnow()),
        Fragment("file5", "file5", 1, utcnow()),
        Fragment("file6", "file6", 1, utcnow()),
    ]
    assert count_files_removed(prev_list, curr_list) == 3
