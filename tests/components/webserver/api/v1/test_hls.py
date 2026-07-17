"""Test the HLS API handler."""
from __future__ import annotations

import datetime
import json
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import delete, insert, update

from viseron.components.storage.models import FileLocations, Files, Recordings
from viseron.components.webserver.api.v1.hls import (
    _init_file_url,
    adjust_fragment_paths,
    count_discontinuities_removed,
    count_files_removed,
)
from viseron.domains.camera.const import CONFIG_LOOKBACK, CONFIG_RECORDER
from viseron.domains.camera.fragmenter import Fragment, generate_playlist
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
        assert response_string.count("/api/v1/hls/segments/") == 3
        assert "?first_tier_path=" not in response_string
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
        assert response_string.count("#EXT-X-DISCONTINUITY") == 1

    def test_get_recording_hls_playlist_no_fragments_skips_init_lookup(self):
        """Test getting a recording HLS playlist with no fragments."""
        with self._get_db_session() as session:
            session.execute(delete(Files))
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
        ) as mock_get_init_file:
            response = self.fetch("/api/v1/hls/test/1/index.m3u8")

        assert response.code == 404
        mock_get_init_file.assert_not_called()

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
                file_result = session.execute(
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
                file_id = file_result.inserted_primary_key[0]
                session.execute(
                    insert(FileLocations).values(
                        file_id=file_id,
                        tier_id=0,
                        tier_path="/test/",
                        path=f"/test/{filename}",
                        directory="test",
                        filename=filename,
                        size=10,
                        state="available",
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

    def _get_hls_playlist_time_period(
        self,
        start_timestamp,
        end_timestamp,
        date,
        expected_files_count,
        expected_end_tag=0,
    ):
        """Test getting HLS playlist."""
        start = int(self._now.timestamp()) + start_timestamp
        end = (
            int(self._now.timestamp()) + end_timestamp
            if end_timestamp is not None
            else None
        )
        url = f"/api/v1/hls/test/index.m3u8?start_timestamp={start}"
        if end is not None:
            url += f"&end_timestamp={end}"
        if date is not None:
            url += f"&date={date}"
        mocked_camera = MockCamera(
            identifier="test",
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
            return_value=self._simulated_now,
        ):
            response = self.fetch(url)

        assert response.code == 200
        response_string = response.body.decode()
        assert response_string.count("#EXTINF") == expected_files_count
        assert response_string.count("#EXT-X-ENDLIST") == expected_end_tag

    # Can't use parametrize for these test because we derive from unittest.TestCase
    def test_get_hls_playlist_time_period_start(self):
        """Test getting HLS playlist for a specific time period."""
        self._get_hls_playlist_time_period(60, None, None, 4)

    def test_get_hls_playlist_time_period_end(self):
        """Test getting HLS playlist for a specific time period with end."""
        self._get_hls_playlist_time_period(0, 60, None, 12, 1)

    def test_get_hls_playlist_time_period_date_today(self):
        """Test getting HLS playlist for a specific time period with date today."""
        self._get_hls_playlist_time_period(0, None, self._now.date().isoformat(), 15, 0)

    def test_get_hls_playlist_time_period_date_not_today(self):
        """Test getting HLS playlist for a specific time period with date not today."""
        self._get_hls_playlist_time_period(0, None, "2023-10-01", 0, 1)

    def test_get_hls_playlist_time_period_no_fragments_skips_init_lookup(self):
        """Test getting HLS playlist for a time period with no fragments."""
        with self._get_db_session() as session:
            session.execute(delete(Files))
            session.commit()

        mocked_camera = MockCamera(
            identifier="test",
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
        ) as mock_get_init_file:
            response = self.fetch(
                "/api/v1/hls/test/index.m3u8?"
                f"start_timestamp={int(self._now.timestamp())}"
            )

        assert response.code == 404
        mock_get_init_file.assert_not_called()


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


def test_count_discontinuities_removed_no_gap():
    """Test count_discontinuities_removed with no removed discontinuity."""
    now = utcnow()
    prev_list = [
        Fragment("file1", "file1", 5, now),
        Fragment("file2", "file2", 5, now + datetime.timedelta(seconds=5)),
        Fragment("file3", "file3", 5, now + datetime.timedelta(seconds=10)),
    ]
    curr_list = [
        Fragment("file2", "file2", 5, now + datetime.timedelta(seconds=5)),
        Fragment("file3", "file3", 5, now + datetime.timedelta(seconds=10)),
    ]

    assert count_discontinuities_removed(prev_list, curr_list) == 0


def test_count_discontinuities_removed_gap_before_new_first():
    """Test count_discontinuities_removed counts removed gap boundary."""
    now = utcnow()
    prev_list = [
        Fragment("file1", "file1", 5, now),
        Fragment("file2", "file2", 5, now + datetime.timedelta(seconds=20)),
        Fragment("file3", "file3", 5, now + datetime.timedelta(seconds=25)),
    ]
    curr_list = [
        Fragment("file3", "file3", 5, now + datetime.timedelta(seconds=25)),
    ]

    assert count_discontinuities_removed(prev_list, curr_list) == 1


def test_count_discontinuities_removed_no_overlap_counts_forward_gap():
    """Test count_discontinuities_removed includes forward gap with no overlap."""
    now = utcnow()
    prev_list = [
        Fragment("file1", "file1", 5, now),
        Fragment("file2", "file2", 5, now + datetime.timedelta(seconds=20)),
    ]
    curr_list = [
        Fragment("file3", "file3", 5, now + datetime.timedelta(seconds=40)),
    ]

    assert count_discontinuities_removed(prev_list, curr_list) == 2


def test_count_discontinuities_removed_init_change():
    """Test removed init changes count as discontinuities."""
    now = utcnow()
    prev_list = [
        Fragment("file1", "file1", 5, now, "/init-a.mp4"),
        Fragment(
            "file2",
            "file2",
            5,
            now + datetime.timedelta(seconds=5),
            "/init-b.mp4",
        ),
        Fragment(
            "file3",
            "file3",
            5,
            now + datetime.timedelta(seconds=10),
            "/init-b.mp4",
        ),
    ]
    curr_list = [
        Fragment(
            "file3",
            "file3",
            5,
            now + datetime.timedelta(seconds=10),
            "/init-b.mp4",
        ),
    ]

    assert count_discontinuities_removed(prev_list, curr_list) == 1


def test_adjust_fragment_paths_uses_hls_file_id_urls():
    """Test HLS fragments use logical segment URLs."""
    files = [
        SimpleNamespace(
            id=123,
            tier_id=0,
            filename="1.m4s",
            duration=5,
            orig_ctime=utcnow(),
            hls_init_hash=None,
        )
    ]

    fragments = adjust_fragment_paths(MockCamera(identifier="test"), "/subpath", files)

    assert fragments[0].path == "/subpath/api/v1/hls/segments/123.m4s"


def test_adjust_fragment_paths_stable_across_tier_move():
    """Test HLS segment URL remains stable when physical tier fields change."""
    orig_ctime = utcnow()
    before_move = [
        SimpleNamespace(
            id=123,
            tier_id=0,
            path="/segments/test/1.m4s",
            filename="1.m4s",
            duration=5,
            orig_ctime=orig_ctime,
            hls_init_hash=None,
        )
    ]
    after_move = [
        SimpleNamespace(
            id=123,
            tier_id=1,
            path="/remote/segments/test/1.m4s",
            filename="1.m4s",
            duration=5,
            orig_ctime=orig_ctime,
            hls_init_hash=None,
        )
    ]

    before_fragments = adjust_fragment_paths(
        MockCamera(identifier="test"), "/subpath", before_move
    )
    after_fragments = adjust_fragment_paths(
        MockCamera(identifier="test"), "/subpath", after_move
    )

    assert before_fragments[0].path == after_fragments[0].path
    assert after_fragments[0].path == "/subpath/api/v1/hls/segments/123.m4s"


def test_init_file_url_uses_camera_and_first_fragment_tier():
    """Test HLS init URL does not expose filesystem paths."""
    camera = MockCamera(identifier="test")
    files = [SimpleNamespace(tier_id=2, hls_init_hash=None)]

    assert _init_file_url(camera, "/subpath", files) == (
        "/subpath/api/v1/hls/init/test/2.mp4"
    )


def test_init_file_url_uses_camera_and_init_hash():
    """Test hash-addressed HLS init URL."""
    camera = MockCamera(identifier="test")
    files = [SimpleNamespace(tier_id=2, hls_init_hash="a" * 64)]

    assert _init_file_url(camera, "/subpath", files) == (
        f"/subpath/api/v1/hls/init/test/{'a' * 64}.mp4"
    )


def test_adjust_fragment_paths_adds_hash_init_url():
    """Test HLS fragments carry hash-addressed init URLs."""
    files = [
        SimpleNamespace(
            id=123,
            tier_id=0,
            filename="1.m4s",
            duration=5,
            orig_ctime=utcnow(),
            hls_init_hash="b" * 64,
        )
    ]

    fragments = adjust_fragment_paths(MockCamera(identifier="test"), "/subpath", files)

    assert fragments[0].init_file == f"/subpath/api/v1/hls/init/test/{'b' * 64}.mp4"


def test_generate_playlist_emits_new_map_when_init_changes():
    """Test playlist switches EXT-X-MAP when fragment init changes."""
    now = utcnow()
    playlist = generate_playlist(
        [
            Fragment("1.m4s", "/segments/1.m4s", 5, now, "/init-a.mp4"),
            Fragment(
                "2.m4s",
                "/segments/2.m4s",
                5,
                now + datetime.timedelta(seconds=5),
                "/init-b.mp4",
            ),
        ],
        "/fallback-init.mp4",
    )

    assert playlist.count("#EXT-X-MAP") == 2
    assert '#EXT-X-MAP:URI="/init-a.mp4"' in playlist
    assert '#EXT-X-MAP:URI="/init-b.mp4"' in playlist
    assert playlist.count("#EXT-X-DISCONTINUITY") == 1
