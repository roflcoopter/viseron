"""Test the HLS API handler."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import delete, insert, update

from viseron.components.storage.models import Files, Recordings
from viseron.components.webserver.api.v1.hls import (
    _get_init_file,
    count_files_removed,
)
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import CONFIG_LOOKBACK, CONFIG_RECORDER
from viseron.domains.camera.fragmenter import Fragment
from viseron.helpers import utcnow

from tests.common import BaseTestWithRecordings, MockCamera
from tests.components.webserver.common import TestAppBaseNoAuth

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


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
