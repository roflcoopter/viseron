"""Test the HLS API handler."""

from __future__ import annotations

import datetime
import json
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import delete, insert, update

from viseron.components.storage.models import Files, Recordings
from viseron.components.webserver.api.v1.hls import (
    HlsAPIHandler,
    _get_init_file,
    count_files_removed,
    update_hls_client,
)
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import CONFIG_LOOKBACK, CONFIG_RECORDER
from viseron.domains.camera.fragmenter import Fragment
from viseron.helpers import utcnow

from tests.common import BaseTestWithRecordings, MockCamera
from tests.components.webserver.common import TestAppBaseNoAuth

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker
    from tornado.httpclient import HTTPResponse


class TestHlsApiHandler(TestAppBaseNoAuth, BaseTestWithRecordings):
    """Test the HLS API handler."""

    def test_get_recording_hls_playlist(self):
        """Test getting a recording HLS playlist."""
        mocked_camera = MockCamera(
            identifier="test", config={CONFIG_RECORDER: {CONFIG_LOOKBACK: 5}}
        )
        with (
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_camera"
                ),
                return_value=mocked_camera,
            ),
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_session"
                ),
                return_value=self._get_db_session(),
            ),
            patch(
                "viseron.components.webserver.api.v1.hls._get_init_file",
                return_value="/test/init.mp4",
            ),
        ):
            response = self.fetch("/api/v1/hls/test/1/index.m3u8")
        assert response.code == 200
        response_string = response.body.decode()
        assert response_string.count("#EXTINF") == 3
        assert response_string.count("#EXT-X-ENDLIST") == 1

    def test_get_recording_hls_playlist_gap_segments(self):
        """Test getting a recording HLS playlist with gap in segments."""
        with self._get_db_session() as session:
            session.execute(delete(Files).where(Files.id.in_([15, 17, 19, 21])))
            session.commit()

        mocked_camera = MockCamera(
            identifier="test", config={CONFIG_RECORDER: {CONFIG_LOOKBACK: 5}}
        )
        with (
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_camera"
                ),
                return_value=mocked_camera,
            ),
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_session"
                ),
                return_value=self._get_db_session(),
            ),
            patch(
                "viseron.components.webserver.api.v1.hls._get_init_file",
                return_value="/test/init.mp4",
            ),
            patch(
                "viseron.components.storage.queries.utcnow",
                return_value=self._now + datetime.timedelta(seconds=3600),
            ),
        ):
            response = self.fetch(
                "/api/v1/hls/test/index.m3u8?start_timestamp="
                f"{int(self._now.timestamp())}"
            )
        assert response.code == 200
        response_string = response.body.decode()
        assert response_string.count("#EXTINF") == 11
        assert response_string.count("#EXT-X-DISCONTINUITY") == 1

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
        with (
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_camera"
                ),
                return_value=mocked_camera,
            ),
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_session"
                ),
                return_value=self._get_db_session(),
            ),
            patch(
                "viseron.components.webserver.api.v1.hls._get_init_file",
                return_value="/test/init.mp4",
            ),
            patch(
                "viseron.components.webserver.api.v1.hls.utcnow",
                return_value=self._now + datetime.timedelta(seconds=36),
            ),
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

        with (
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_camera"
                ),
                return_value=mocked_camera,
            ),
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_session"
                ),
                return_value=self._get_db_session(),
            ),
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
        with (
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_camera"
                ),
                return_value=mocked_camera,
            ),
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_session"
                ),
                return_value=self._get_db_session(),
            ),
            patch(
                "viseron.components.webserver.api.v1.hls._get_init_file",
                return_value="/test/init.mp4",
            ),
            patch(
                "viseron.components.storage.queries.utcnow",
                return_value=self._simulated_now,
            ),
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

    def _fetch_playlist(
        self,
        url: str,
        now: datetime.datetime,
        hls_client_id: str | None = None,
        init_file: str | None = "/test/init.mp4",
    ) -> HTTPResponse:
        """Fetch a playlist, optionally as a tracked HLS client."""
        headers = {"Hls-Client-Id": hls_client_id} if hls_client_id else None
        mocked_camera = MockCamera(
            identifier="test", config={CONFIG_RECORDER: {CONFIG_LOOKBACK: 5}}
        )
        with (
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_camera"
                ),
                return_value=mocked_camera,
            ),
            patch(
                (
                    "viseron.components.webserver.request_handler.ViseronRequestHandler"
                    "._get_session"
                ),
                return_value=self._get_db_session(),
            ),
            patch(
                "viseron.components.webserver.api.v1.hls._get_init_file",
                return_value=init_file,
            ),
            patch("viseron.components.webserver.api.v1.hls.utcnow", return_value=now),
            patch("viseron.components.storage.queries.utcnow", return_value=now),
        ):
            return self.fetch(url, headers=headers)

    def _time_period_url(self, query: str) -> str:
        return (
            f"/api/v1/hls/test/index.m3u8?start_timestamp={int(self._now.timestamp())}"
            f"&{query}"
        )

    def test_get_hls_playlist_time_period_delta_update(self):
        """Test that a known client gets a Playlist Delta Update."""
        url = self._time_period_url(
            f"date={self._now.date().isoformat()}&_HLS_skip=YES"
        )
        hls_client_id = str(uuid.uuid4())

        first = self._fetch_playlist(url, self._simulated_now, hls_client_id)
        second = self._fetch_playlist(url, self._simulated_now, hls_client_id)

        assert first.code == 200
        first_playlist = first.body.decode()
        # The first request has no previous playlist to fill in skipped segments
        assert first_playlist.count("#EXTINF") == 15
        assert first_playlist.count("#EXT-X-SERVER-CONTROL:CAN-SKIP-UNTIL=30") == 1
        assert first_playlist.count("#EXT-X-SKIP") == 0
        assert second.code == 200
        second_playlist = second.body.decode()
        assert second_playlist.count("#EXTINF") == 6
        assert second_playlist.count("#EXT-X-SKIP:SKIPPED-SEGMENTS=9") == 1
        assert second_playlist.count("#EXT-X-VERSION:9") == 1
        assert second_playlist.count("#EXT-X-MAP") == 1
        assert second_playlist.count("#EXT-X-MEDIA-SEQUENCE:0") == 1

    def test_get_hls_playlist_time_period_skip_after_failed_request(self):
        """Test that a client is only tracked once it has received a playlist."""
        url = self._time_period_url(
            f"date={self._now.date().isoformat()}&_HLS_skip=YES"
        )
        hls_client_id = str(uuid.uuid4())

        failed = self._fetch_playlist(
            url, self._simulated_now, hls_client_id, init_file=None
        )
        response = self._fetch_playlist(url, self._simulated_now, hls_client_id)

        assert failed.code == 404
        assert response.code == 200
        playlist = response.body.decode()
        assert playlist.count("#EXTINF") == 15
        assert playlist.count("#EXT-X-SKIP") == 0

    def _fetch_stale_client_delta_update(self, removed_files: int) -> str:
        """Fetch a delta update for a client whose previous playlist is outdated.

        The first removed_files are deleted from the database between the requests.
        """
        url = self._time_period_url("_HLS_skip=YES")
        hls_client_id = str(uuid.uuid4())

        first = self._fetch_playlist(
            url, self._now + datetime.timedelta(seconds=17), hls_client_id
        )
        with self._get_db_session() as session:
            session.execute(
                delete(Files)
                .where(Files.camera_identifier == "test")
                .where(
                    Files.orig_ctime
                    < self._now + datetime.timedelta(seconds=5 * removed_files)
                )
            )
            session.commit()
        second = self._fetch_playlist(url, self._simulated_now, hls_client_id)

        # The first playlist ends long before the skip boundary of the second one
        assert first.body.decode().count("#EXTINF") == 4
        assert second.code == 200
        return second.body.decode()

    def test_get_hls_playlist_time_period_stale_client_delta_update(self):
        """Test that a stale client only skips segments it already received."""
        playlist = self._fetch_stale_client_delta_update(removed_files=0)

        assert playlist.count("#EXTINF") == 11
        assert playlist.count("#EXT-X-SKIP:SKIPPED-SEGMENTS=4") == 1
        assert playlist.count("#EXT-X-MEDIA-SEQUENCE:0") == 1

    def test_get_hls_playlist_time_period_no_overlap_delta_update(self):
        """Test that a full playlist is sent when no received segments remain."""
        playlist = self._fetch_stale_client_delta_update(removed_files=4)

        assert playlist.count("#EXTINF") == 11
        assert playlist.count("#EXT-X-SKIP") == 0
        assert playlist.count("#EXT-X-MEDIA-SEQUENCE:4") == 1

    def test_get_hls_playlist_time_period_skip_without_client_id(self):
        """Test that skipping is ignored when the client is not tracked."""
        url = self._time_period_url(
            f"date={self._now.date().isoformat()}&_HLS_skip=YES"
        )

        response = self._fetch_playlist(url, self._simulated_now)

        assert response.code == 200
        playlist = response.body.decode()
        assert playlist.count("#EXTINF") == 15
        assert playlist.count("#EXT-X-SERVER-CONTROL") == 0
        assert playlist.count("#EXT-X-SKIP") == 0

    def test_get_hls_playlist_time_period_ended_skip(self):
        """Test that ended playlists never advertise or use delta updates."""
        end = int(self._now.timestamp()) + 60
        url = self._time_period_url(f"end_timestamp={end}&_HLS_skip=YES")
        hls_client_id = str(uuid.uuid4())

        self._fetch_playlist(url, self._simulated_now, hls_client_id)
        response = self._fetch_playlist(url, self._simulated_now, hls_client_id)

        assert response.code == 200
        playlist = response.body.decode()
        assert playlist.count("#EXTINF") == 12
        assert playlist.count("#EXT-X-SERVER-CONTROL") == 0
        assert playlist.count("#EXT-X-SKIP") == 0
        assert playlist.count("#EXT-X-ENDLIST") == 1

    def test_get_hls_playlist_time_period_invalid_skip(self):
        """Test that an invalid _HLS_skip value is rejected."""
        url = self._time_period_url("_HLS_skip=NO")

        response = self._fetch_playlist(url, self._simulated_now)

        assert response.code == 400

    def test_get_recording_hls_ongoing_delta_update(self):
        """Test that a known client gets a Playlist Delta Update for a recording."""
        recording_id = 3
        with self._get_db_session() as session:
            session.execute(
                update(Recordings)
                .values(end_time=None)
                .where(Recordings.id == recording_id)
            )
            session.commit()
        url = f"/api/v1/hls/test/{recording_id}/index.m3u8?_HLS_skip=YES"
        now = self._now + datetime.timedelta(seconds=36)
        hls_client_id = str(uuid.uuid4())

        # The fixture recording is too short for the real skip boundary
        with patch(
            (
                "viseron.components.webserver.api.v1.hls"
                ".HLS_SKIP_BOUNDARY_TARGET_DURATIONS"
            ),
            2,
        ):
            first = self._fetch_playlist(url, now, hls_client_id)
            second = self._fetch_playlist(url, now, hls_client_id)

        assert first.code == 200
        first_playlist = first.body.decode()
        assert first_playlist.count("#EXTINF") == 4
        assert first_playlist.count("#EXT-X-SERVER-CONTROL:CAN-SKIP-UNTIL=10") == 1
        assert second.code == 200
        second_playlist = second.body.decode()
        assert second_playlist.count("#EXTINF") == 2
        assert second_playlist.count("#EXT-X-SKIP:SKIPPED-SEGMENTS=2") == 1
        assert second_playlist.count("#EXT-X-ENDLIST") == 0


def _named_fragments(names: list[int]) -> list[Fragment]:
    return [Fragment(f"{name}.m4s", f"/test/{name}.m4s", 5, utcnow()) for name in names]


@pytest.mark.parametrize(
    ("previous_playlists", "current", "expected_received", "expected_media_sequence"),
    [
        pytest.param([], [1, 2, 3], 0, 0, id="new_client"),
        pytest.param([[]], [1, 2], 0, 0, id="previous_playlist_empty"),
        pytest.param([[1, 2, 3]], [1, 2, 3], 3, 0, id="unchanged"),
        pytest.param([[1, 2, 3]], [1, 2, 3, 4], 3, 0, id="fragments_appended"),
        pytest.param([[1, 2, 3]], [2, 3, 4], 2, 1, id="head_removed"),
        pytest.param([[1, 2, 3]], [4, 5], 0, 3, id="no_overlap"),
        pytest.param([[1, 2, 3, 4]], [1, 3, 4], 1, 0, id="middle_removed"),
        pytest.param([[1, 2], [2, 3]], [3, 4], 1, 2, id="media_sequence_accumulates"),
    ],
)
def test_update_hls_client(
    previous_playlists: list[list[int]],
    current: list[int],
    expected_received: int,
    expected_media_sequence: int,
) -> None:
    """Test the leading fragments a client received and its media sequence."""
    hls_client_id = str(uuid.uuid4())
    for previous in previous_playlists:
        update_hls_client(hls_client_id, _named_fragments(previous))

    hls_client, received = update_hls_client(hls_client_id, _named_fragments(current))

    assert received == expected_received
    assert hls_client.media_sequence == expected_media_sequence
    assert HlsAPIHandler.hls_client_ids[hls_client_id] is hls_client


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


class SegmentFile(NamedTuple):
    """Segment file row to insert for _get_init_file tests."""

    tier_id: int
    directory: str
    age_seconds: int
    camera_identifier: str = "test"
    subcategory: str = "segments"


def _insert_segment_files(
    get_session: sessionmaker[Session], root: Path, files: list[SegmentFile]
) -> None:
    now = utcnow()
    with get_session() as session:
        for index, file in enumerate(files):
            directory = os.path.join(root, file.directory)
            timestamp = now - datetime.timedelta(seconds=file.age_seconds)
            session.execute(
                insert(Files).values(
                    tier_id=file.tier_id,
                    tier_path=str(root),
                    camera_identifier=file.camera_identifier,
                    category="recorder",
                    subcategory=file.subcategory,
                    path=os.path.join(directory, f"{index}.m4s"),
                    directory=directory,
                    filename=f"{index}.m4s",
                    size=10,
                    orig_ctime=timestamp,
                    duration=5,
                    created_at=timestamp,
                )
            )
        session.commit()


def _create_init_files(root: Path, directories: list[str]) -> None:
    for directory in directories:
        os.makedirs(os.path.join(root, directory), exist_ok=True)
        Path(os.path.join(root, directory, "init.mp4")).touch()


@pytest.mark.parametrize(
    ("files", "init_directories", "expected_directory"),
    [
        pytest.param(
            [SegmentFile(1, "a_tier1", 0), SegmentFile(0, "b_tier0", 100)],
            ["a_tier1", "b_tier0"],
            "b_tier0",
            id="lowest_tier_preferred_over_newer_files",
        ),
        pytest.param(
            [
                SegmentFile(1, "c_tier1", 50),
                SegmentFile(2, "b_tier2", 0),
                SegmentFile(0, "a_tier0", 100),
            ],
            ["b_tier2", "c_tier1"],
            "c_tier1",
            id="next_lowest_tier_when_init_missing",
        ),
        pytest.param(
            [
                SegmentFile(0, "b_newest_file", 100),
                SegmentFile(0, "a_older_files", 10),
                SegmentFile(0, "b_newest_file", 5),
            ],
            ["a_older_files", "b_newest_file"],
            "b_newest_file",
            id="same_tier_newest_file_preferred",
        ),
        pytest.param(
            [
                SegmentFile(0, "a_other_camera", 0, camera_identifier="other"),
                SegmentFile(0, "b_thumbnails", 0, subcategory="thumbnails"),
                SegmentFile(1, "c_tier1", 100),
            ],
            ["a_other_camera", "b_thumbnails", "c_tier1"],
            "c_tier1",
            id="other_cameras_and_subcategories_ignored",
        ),
    ],
)
def test_get_init_file(
    get_db_session: sessionmaker[Session],
    tmp_path: Path,
    files: list[SegmentFile],
    init_directories: list[str],
    expected_directory: str,
) -> None:
    """Test that the init file is taken from the lowest tier with an init file."""
    _insert_segment_files(get_db_session, tmp_path, files)
    _create_init_files(tmp_path, init_directories)

    assert _get_init_file(get_db_session, MockCamera(identifier="test")) == (
        os.path.join(tmp_path, expected_directory, "init.mp4")
    )


def test_get_init_file_not_found(
    get_db_session: sessionmaker[Session], tmp_path: Path
) -> None:
    """Test that None is returned when no directory contains an init file."""
    _insert_segment_files(
        get_db_session,
        tmp_path,
        [SegmentFile(0, "tier0", 0), SegmentFile(1, "tier1", 0)],
    )

    assert _get_init_file(get_db_session, MockCamera(identifier="test")) is None


def test_get_init_file_first_tier(tmp_path: Path) -> None:
    """Test that the first tier init file is returned without querying the DB."""
    _create_init_files(tmp_path, ["tier0"])
    camera = MockCamera(
        identifier="test",
        spec=AbstractCamera,
        segments_folder=os.path.join(tmp_path, "tier0"),
    )
    get_session = MagicMock()

    assert _get_init_file(get_session, camera) == os.path.join(
        tmp_path, "tier0", "init.mp4"
    )
    get_session.assert_not_called()


def test_get_init_file_first_tier_missing(
    get_db_session: sessionmaker[Session], tmp_path: Path
) -> None:
    """Test that the DB is queried when the first tier has no init file."""
    _insert_segment_files(
        get_db_session,
        tmp_path,
        [SegmentFile(0, "a_tier0", 0), SegmentFile(1, "b_tier1", 100)],
    )
    _create_init_files(tmp_path, ["b_tier1"])
    camera = MockCamera(
        identifier="test",
        spec=AbstractCamera,
        segments_folder=os.path.join(tmp_path, "a_tier0"),
    )

    assert _get_init_file(get_db_session, camera) == os.path.join(
        tmp_path, "b_tier1", "init.mp4"
    )
