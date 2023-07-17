"""Test the query functions."""
import datetime
from typing import Any, Generator

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from viseron.components.storage.models import Files, Recordings
from viseron.components.storage.queries import (
    files_to_move_query,
    recordings_to_move_query,
)


class TestMoveQueries:
    """Test the moving of files query functions."""

    _session: Session
    _now: datetime.datetime

    @pytest.fixture(autouse=True, scope="class")
    def setup_class_fixture(
        self, db_session_class: Session
    ) -> Generator[None, Any, None]:
        """Insert data used by all tests."""
        TestMoveQueries._session = db_session_class
        TestMoveQueries._now = datetime.datetime.now()

        for i in range(15):
            filename = f"test{i}.mp4"
            db_session_class.execute(
                insert(Files).values(
                    tier_id=1,
                    camera_identifier="test",
                    category="recorder",
                    path=f"/test/{filename}",
                    directory="test",
                    filename=filename,
                    size=10,
                    created_at=self._now + datetime.timedelta(seconds=5 * i),
                )
            )
            db_session_class.execute(
                insert(Files).values(
                    tier_id=1,
                    camera_identifier="test2",
                    category="recorder",
                    path=f"/test2/{filename}",
                    directory="test2",
                    filename=filename,
                    size=10,
                    created_at=self._now + datetime.timedelta(seconds=5 * i),
                )
            )

        # Insert some recordings
        self._session.execute(
            insert(Recordings).values(
                camera_identifier="test",
                start_time=self._now + datetime.timedelta(seconds=7),
                end_time=self._now + datetime.timedelta(seconds=10),
                created_at=self._now + datetime.timedelta(seconds=7),
            )
        )
        self._session.execute(
            insert(Recordings).values(
                camera_identifier="test",
                start_time=self._now + datetime.timedelta(seconds=26),
                end_time=self._now + datetime.timedelta(seconds=36),
                created_at=self._now + datetime.timedelta(seconds=26),
            )
        )
        self._session.execute(
            insert(Recordings).values(
                camera_identifier="test",
                start_time=self._now + datetime.timedelta(seconds=40),
                end_time=self._now + datetime.timedelta(seconds=45),
                created_at=self._now + datetime.timedelta(seconds=40),
            )
        )
        yield

    def test_files_to_move_query(self) -> None:
        """Test files_to_move_query."""
        min_age_timestamp = (self._now + datetime.timedelta(seconds=15)).timestamp()
        stmt = files_to_move_query(
            category="recorder",
            tier_id=1,
            camera_identifier="test",
            max_bytes=1,
            min_age_timestamp=min_age_timestamp,
            min_bytes=0,
            max_age_timestamp=0,
        )
        results = self._session.execute(stmt).fetchall()

        assert len(results) == 4
        assert results[0].id == 1
        assert results[0].path == "/test/test0.mp4"
        assert results[1].id == 3
        assert results[1].path == "/test/test1.mp4"
        assert results[2].id == 5
        assert results[2].path == "/test/test2.mp4"
        assert results[3].id == 7
        assert results[3].path == "/test/test3.mp4"

    def test_recordings_to_move_query_max_bytes(self) -> None:
        """Test recordings_to_move_query using max_bytes."""
        min_age_timestamp = (self._now + datetime.timedelta(seconds=360)).timestamp()
        stmt = recordings_to_move_query(
            segment_length=5,
            tier_id=1,
            camera_identifier="test",
            max_bytes=80,
            min_age_timestamp=min_age_timestamp,
            max_age_timestamp=0,
            min_bytes=0,
        )
        results = self._session.execute(stmt).fetchall()
        assert len(results) == 13
        assert results[0].recording_id is None
        assert results[0].file_id == 1
        assert results[1].recording_id == 1
        assert results[1].file_id == 3
        assert results[2].recording_id == 1
        assert results[2].file_id == 5
        assert results[3].recording_id == 1
        assert results[3].file_id == 7
        assert results[4].recording_id is None
        assert results[4].file_id == 9

    def test_recordings_to_move_query_min_age(self) -> None:
        """Test recordings_to_move_query using max_bytes + min_age."""
        min_age_timestamp = (self._now + datetime.timedelta(seconds=7)).timestamp()
        stmt = recordings_to_move_query(
            segment_length=5,
            tier_id=1,
            camera_identifier="test",
            max_bytes=80,
            min_age_timestamp=min_age_timestamp,
            max_age_timestamp=0,
            min_bytes=0,
        )
        results = self._session.execute(stmt).fetchall()
        assert len(results) == 9
        assert results[0].recording_id is None
        assert results[0].file_id == 1
        assert results[1].recording_id == 1
        assert results[1].file_id == 3
        assert results[2].recording_id == 1
        assert results[2].file_id == 5
        assert results[3].recording_id == 1
        assert results[3].file_id == 7
        assert results[4].recording_id is None
        assert results[4].file_id == 9

    def test_recordings_to_move_query_max_age(self) -> None:
        """Test recordings_to_move_query using max_age."""
        max_age_timestamp = (self._now + datetime.timedelta(seconds=26)).timestamp()
        stmt = recordings_to_move_query(
            segment_length=5,
            tier_id=1,
            camera_identifier="test",
            max_bytes=0,
            min_age_timestamp=self._now.timestamp(),
            max_age_timestamp=max_age_timestamp,
            min_bytes=0,
        )
        results = self._session.execute(stmt).fetchall()
        assert len(results) == 13
        assert results[0].recording_id is None
        assert results[0].file_id == 1
        assert results[1].recording_id == 1
        assert results[1].file_id == 3
        assert results[2].recording_id == 1
        assert results[2].file_id == 5
        assert results[3].recording_id == 1
        assert results[3].file_id == 7
        assert results[4].recording_id is None
        assert results[4].file_id == 9

    def test_recordings_to_move_query_min_bytes(self) -> None:
        """Test recordings_to_move_query using max_age + min_bytes.

        max_age only would return 13 segments, but min_bytes will make sure that
        only the recordings that exceed a total storage space of 100 will be included,
        for a total of 1 recording and 3 files to delete.
        """
        max_age_timestamp = (self._now + datetime.timedelta(seconds=26)).timestamp()
        stmt = recordings_to_move_query(
            segment_length=5,
            tier_id=1,
            camera_identifier="test",
            max_bytes=0,
            min_age_timestamp=self._now.timestamp(),
            max_age_timestamp=max_age_timestamp,
            min_bytes=100,
        )
        results = self._session.execute(stmt).fetchall()
        assert len(results) == 9
        assert results[0].recording_id is None
        assert results[0].file_id == 1
        assert results[1].recording_id == 1
        assert results[1].file_id == 3
        assert results[2].recording_id == 1
        assert results[2].file_id == 5
        assert results[3].recording_id == 1
        assert results[3].file_id == 7
        assert results[4].recording_id is None
        assert results[4].file_id == 9
        assert results[5].recording_id is None
        assert results[5].file_id == 23
        assert results[8].recording_id is None
        assert results[8].file_id == 29

    def test_recordings_to_move_query_max_bytes_and_age(self) -> None:
        """Test recordings_to_move_query using max_bytes + max_age."""
        min_age_timestamp = (self._now + datetime.timedelta(seconds=360)).timestamp()
        max_age_timestamp = (self._now + datetime.timedelta(seconds=26)).timestamp()
        stmt = recordings_to_move_query(
            segment_length=5,
            tier_id=1,
            camera_identifier="test",
            max_bytes=110,
            min_age_timestamp=min_age_timestamp,
            max_age_timestamp=max_age_timestamp,
            min_bytes=0,
        )
        results = self._session.execute(stmt).fetchall()
        assert len(results) == 13
        assert results[0].recording_id is None
        assert results[0].file_id == 1
        assert results[1].recording_id == 1
        assert results[1].file_id == 3
        assert results[2].recording_id == 1
        assert results[2].file_id == 5
        assert results[3].recording_id == 1
        assert results[3].file_id == 7
        assert results[4].recording_id is None
        assert results[4].file_id == 9
        assert results[5].recording_id == 2
        assert results[5].file_id == 11
        assert results[6].recording_id == 2
        assert results[6].file_id == 13
        assert results[7].recording_id == 2
        assert results[7].file_id == 15
        assert results[8].recording_id == 2
        assert results[8].file_id == 17
        assert results[9].recording_id is None
        assert results[9].file_id == 23
        assert results[12].recording_id is None
        assert results[12].file_id == 29
