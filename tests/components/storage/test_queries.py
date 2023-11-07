"""Test the query functions."""
import datetime

from sqlalchemy import insert, update

from viseron.components.storage.models import Files, FilesMeta, Recordings
from viseron.components.storage.queries import (
    files_to_move_query,
    get_recording_fragments,
    recordings_to_move_query,
)

from tests.common import BaseTestWithRecordings


class TestMoveQueries(BaseTestWithRecordings):
    """Test the moving of files query functions."""

    def test_files_to_move_query(self) -> None:
        """Test files_to_move_query."""
        min_age_timestamp = (self._now + datetime.timedelta(seconds=15)).timestamp()
        stmt = files_to_move_query(
            category="recorder",
            tier_id=0,
            camera_identifier="test",
            max_bytes=1,
            min_age_timestamp=min_age_timestamp,
            min_bytes=0,
            max_age_timestamp=0,
        )
        with self._get_db_session() as session:
            results = session.execute(stmt).fetchall()

        assert len(results) == 4
        assert results[0].id == 1
        assert results[1].id == 3
        assert results[2].id == 5
        assert results[3].id == 7

    def test_recordings_to_move_query_max_bytes(self) -> None:
        """Test recordings_to_move_query using max_bytes."""
        min_age_timestamp = (self._now + datetime.timedelta(seconds=360)).timestamp()
        stmt = recordings_to_move_query(
            segment_length=5,
            tier_id=0,
            camera_identifier="test",
            lookback=0,
            max_bytes=80,
            min_age_timestamp=min_age_timestamp,
            max_age_timestamp=0,
            min_bytes=0,
        )
        with self._get_db_session() as session:
            results = session.execute(stmt).fetchall()

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
            tier_id=0,
            camera_identifier="test",
            lookback=0,
            max_bytes=80,
            min_age_timestamp=min_age_timestamp,
            max_age_timestamp=0,
            min_bytes=0,
        )
        with self._get_db_session() as session:
            results = session.execute(stmt).fetchall()

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
            tier_id=0,
            camera_identifier="test",
            lookback=0,
            max_bytes=0,
            min_age_timestamp=self._now.timestamp(),
            max_age_timestamp=max_age_timestamp,
            min_bytes=0,
        )
        with self._get_db_session() as session:
            results = session.execute(stmt).fetchall()

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
            tier_id=0,
            camera_identifier="test",
            lookback=0,
            max_bytes=0,
            min_age_timestamp=self._now.timestamp(),
            max_age_timestamp=max_age_timestamp,
            min_bytes=100,
        )
        with self._get_db_session() as session:
            results = session.execute(stmt).fetchall()

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
            tier_id=0,
            camera_identifier="test",
            lookback=0,
            max_bytes=110,
            min_age_timestamp=min_age_timestamp,
            max_age_timestamp=max_age_timestamp,
            min_bytes=0,
        )
        with self._get_db_session() as session:
            results = session.execute(stmt).fetchall()

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
        assert results[5].recording_id == 3
        assert results[5].file_id == 11
        assert results[6].recording_id == 3
        assert results[6].file_id == 13
        assert results[7].recording_id == 3
        assert results[7].file_id == 15
        assert results[8].recording_id == 3
        assert results[8].file_id == 17
        assert results[9].recording_id is None
        assert results[9].file_id == 23
        assert results[12].recording_id is None
        assert results[12].file_id == 29

    def test_recordings_to_move_query_active_recording(self) -> None:
        """Test recordings_to_move_query where end_time is not set."""
        with self._get_db_session() as session:
            session.execute(
                update(Recordings).values(end_time=None).where(Recordings.id == 1)
            )
            session.commit()

        min_age_timestamp = (self._now + datetime.timedelta(seconds=360)).timestamp()
        stmt = recordings_to_move_query(
            segment_length=5,
            tier_id=0,
            camera_identifier="test",
            lookback=0,
            max_bytes=80,
            min_age_timestamp=min_age_timestamp,
            max_age_timestamp=0,
            min_bytes=0,
        )
        with self._get_db_session() as session:
            results = session.execute(stmt).fetchall()
        assert len(results) == 13

    def test_get_recording_fragments(self):
        """Test get_recording_fragments."""
        # Simulate a file that has been moved a up tier but have not been removed
        # from the previous tier yet
        with self._get_db_session() as session:
            created_at = self._now + datetime.timedelta(seconds=55)
            timestamp = self._now + datetime.timedelta(seconds=25)
            filename = f"{int(timestamp.timestamp())}.m4s"
            session.execute(
                insert(Files).values(
                    tier_id=1,
                    camera_identifier="test",
                    category="recorder",
                    path=f"/tier2/{filename}",
                    directory="tier2",
                    filename=filename,
                    size=10,
                    created_at=created_at,
                )
            )
            session.execute(
                insert(FilesMeta).values(
                    path=f"/tier2/{filename}",
                    orig_ctime=timestamp,
                    meta={"m3u8": {"EXTINF": 5}},
                    created_at=created_at,
                )
            )
            session.commit()

        files = get_recording_fragments(3, 5, self._get_db_session)
        assert len(files) == 4
        assert files[0].id == 9
        assert files[1].id == 31
        assert files[1].tier_id == 1
        assert files[2].id == 13
        assert files[3].id == 15
