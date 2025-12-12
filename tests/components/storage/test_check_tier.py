"""Test the query functions."""
import datetime

from sqlalchemy import update

from viseron.components.storage.check_tier import (
    get_files_to_move,
    get_recordings_to_move,
    load_recordings,
    load_tier,
)
from viseron.components.storage.models import Recordings

from tests.common import BaseTestWithRecordings


class TestCheckTier(BaseTestWithRecordings):
    """Test the moving of files query functions."""

    def test_get_files_to_move_max_bytes(self) -> None:
        """Test get_files_to_move using max_bytes."""
        data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        files_to_move = get_files_to_move(
            data=data,
            max_bytes=80,
            min_age_timestamp=self._simulated_now.timestamp(),
            min_bytes=0,
            max_age_timestamp=0,
            drain=False,
        )

        assert len(files_to_move) == 8
        assert files_to_move[0]["id"] == 1
        assert files_to_move[1]["id"] == 3
        assert files_to_move[2]["id"] == 5
        assert files_to_move[3]["id"] == 7
        assert files_to_move[7]["id"] == 15

    def test_get_files_to_move_min_age(self) -> None:
        """Test get_files_to_move using max_bytes + min_age."""
        min_age_timestamp = (self._now + datetime.timedelta(seconds=7)).timestamp()
        data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        files_to_move = get_files_to_move(
            data=data,
            max_bytes=80,
            min_age_timestamp=min_age_timestamp,
            min_bytes=0,
            max_age_timestamp=0,
            drain=False,
        )

        assert len(files_to_move) == 2
        assert files_to_move[0]["id"] == 1
        assert files_to_move[1]["id"] == 3

    def test_get_files_to_move_max_age(self) -> None:
        """Test get_files_to_move using max_age."""
        max_age_timestamp = (self._now + datetime.timedelta(seconds=26)).timestamp()
        data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        files_to_move = get_files_to_move(
            data=data,
            max_bytes=0,
            min_age_timestamp=self._simulated_now.timestamp(),
            min_bytes=0,
            max_age_timestamp=max_age_timestamp,
            drain=False,
        )
        assert len(files_to_move) == 6
        assert files_to_move[0]["id"] == 1
        assert files_to_move[1]["id"] == 3
        assert files_to_move[2]["id"] == 5
        assert files_to_move[5]["id"] == 11

    def test_get_files_to_move_min_bytes(self) -> None:
        """Test get_files_to_move using max_age + min_bytes.

        max_age only would return 6 files, but min_bytes will make sure that
        only the files that exceed a total storage space of 110 will be included,
        for a total of 5 files to delete.
        """
        max_age_timestamp = (self._now + datetime.timedelta(seconds=26)).timestamp()
        data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        files_to_move = get_files_to_move(
            data=data,
            max_bytes=0,
            min_age_timestamp=self._simulated_now.timestamp(),
            min_bytes=110,
            max_age_timestamp=max_age_timestamp,
            drain=False,
        )
        assert len(files_to_move) == 5
        assert files_to_move[0]["id"] == 1
        assert files_to_move[1]["id"] == 3
        assert files_to_move[2]["id"] == 5
        assert files_to_move[4]["id"] == 9

    def test_get_files_to_move_max_bytes_and_age(self) -> None:
        """Test get_files_to_move using max_bytes + max_age.

        max_bytes only would return 8 files, but max_age will make sure that the
        files that are older than 40 seconds are included, for a total of 9 files to
        delete.
        """
        max_age_timestamp = (self._now + datetime.timedelta(seconds=40)).timestamp()
        data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        files_to_move = get_files_to_move(
            data=data,
            max_bytes=80,
            min_age_timestamp=self._simulated_now.timestamp(),
            min_bytes=0,
            max_age_timestamp=max_age_timestamp,
            drain=False,
        )

        assert len(files_to_move) == 9
        assert files_to_move[0]["id"] == 1
        assert files_to_move[1]["id"] == 3
        assert files_to_move[2]["id"] == 5
        assert files_to_move[8]["id"] == 17

    def test_get_files_to_move_drain(self) -> None:
        """Test get_files_to_move using drain."""
        data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        files_to_move = get_files_to_move(
            data=data,
            max_bytes=80,
            min_age_timestamp=self._simulated_now.timestamp(),
            min_bytes=0,
            max_age_timestamp=0,
            drain=True,
        )

        assert len(files_to_move) == len(data)

    def test_get_files_to_move_drain_limit_not_reached(self) -> None:
        """Test get_files_to_move using drain when limit is not reached."""
        data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        files_to_move = get_files_to_move(
            data=data,
            max_bytes=9999,
            min_age_timestamp=self._simulated_now.timestamp(),
            min_bytes=0,
            max_age_timestamp=0,
            drain=True,
        )

        assert len(files_to_move) == 0

    def test_recordings_to_move_query_max_bytes(self) -> None:
        """Test recordings_to_move_query using max_bytes."""
        files_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        recordings_data = load_recordings(
            get_session=self._get_db_session,
            camera_identifier="test",
        )
        files_to_move = get_recordings_to_move(
            recordings_data=recordings_data,
            files_data=files_data,
            segment_length=5,
            max_bytes=80,
            min_age_timestamp=self._simulated_now.timestamp(),
            max_age_timestamp=0,
            min_bytes=0,
            file_min_age_timestamp=self._simulated_now.timestamp(),
            drain=False,
        )

        assert len(files_to_move) == 13
        assert files_to_move[0]["recording_id"] == -1
        assert files_to_move[0]["id"] == 1
        assert files_to_move[1]["recording_id"] == 1
        assert files_to_move[1]["id"] == 3
        assert files_to_move[2]["recording_id"] == 1
        assert files_to_move[2]["id"] == 5
        assert files_to_move[3]["recording_id"] == 1
        assert files_to_move[3]["id"] == 7
        assert files_to_move[4]["recording_id"] == -1
        assert files_to_move[4]["id"] == 9

    def test_recordings_to_move_query_min_age(self) -> None:
        """Test recordings_to_move_query using max_bytes + min_age."""
        min_age_timestamp = (self._now + datetime.timedelta(seconds=7)).timestamp()
        files_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        recordings_data = load_recordings(
            get_session=self._get_db_session,
            camera_identifier="test",
        )
        files_to_move = get_recordings_to_move(
            recordings_data=recordings_data,
            files_data=files_data,
            segment_length=5,
            max_bytes=80,
            min_age_timestamp=min_age_timestamp,
            max_age_timestamp=0,
            min_bytes=0,
            file_min_age_timestamp=self._simulated_now.timestamp(),
            drain=False,
        )

        assert len(files_to_move) == 9
        assert files_to_move[0]["recording_id"] == -1
        assert files_to_move[0]["id"] == 1
        assert files_to_move[1]["recording_id"] == 1
        assert files_to_move[1]["id"] == 3
        assert files_to_move[2]["recording_id"] == 1
        assert files_to_move[2]["id"] == 5
        assert files_to_move[3]["recording_id"] == 1
        assert files_to_move[3]["id"] == 7
        assert files_to_move[4]["recording_id"] == -1
        assert files_to_move[4]["id"] == 9

    def test_recordings_to_move_query_max_age(self) -> None:
        """Test recordings_to_move_query using max_age."""
        max_age_timestamp = (self._now + datetime.timedelta(seconds=26)).timestamp()
        files_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        recordings_data = load_recordings(
            get_session=self._get_db_session,
            camera_identifier="test",
        )
        files_to_move = get_recordings_to_move(
            recordings_data=recordings_data,
            files_data=files_data,
            segment_length=5,
            max_bytes=0,
            min_age_timestamp=self._simulated_now.timestamp(),
            max_age_timestamp=max_age_timestamp,
            min_bytes=0,
            file_min_age_timestamp=self._simulated_now.timestamp(),
            drain=False,
        )

        assert len(files_to_move) == 13
        assert files_to_move[0]["recording_id"] == -1
        assert files_to_move[0]["id"] == 1
        assert files_to_move[1]["recording_id"] == 1
        assert files_to_move[1]["id"] == 3
        assert files_to_move[2]["recording_id"] == 1
        assert files_to_move[2]["id"] == 5
        assert files_to_move[3]["recording_id"] == 1
        assert files_to_move[3]["id"] == 7
        assert files_to_move[4]["recording_id"] == -1
        assert files_to_move[4]["id"] == 9

    def test_recordings_to_move_query_min_bytes(self) -> None:
        """Test recordings_to_move_query using max_age + min_bytes.

        max_age only would return 13 segments, but min_bytes will make sure that
        only the recordings that exceed a total storage space of 100 will be included,
        for a total of 1 recording and 3 files to delete.
        """
        max_age_timestamp = (self._now + datetime.timedelta(seconds=26)).timestamp()

        files_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        recordings_data = load_recordings(
            get_session=self._get_db_session,
            camera_identifier="test",
        )
        files_to_move = get_recordings_to_move(
            recordings_data=recordings_data,
            files_data=files_data,
            segment_length=5,
            max_bytes=0,
            min_age_timestamp=self._simulated_now.timestamp(),
            max_age_timestamp=max_age_timestamp,
            min_bytes=100,
            file_min_age_timestamp=self._simulated_now.timestamp(),
            drain=False,
        )

        assert len(files_to_move) == 9
        assert files_to_move[0]["recording_id"] == -1
        assert files_to_move[0]["id"] == 1
        assert files_to_move[1]["recording_id"] == 1
        assert files_to_move[1]["id"] == 3
        assert files_to_move[2]["recording_id"] == 1
        assert files_to_move[2]["id"] == 5
        assert files_to_move[3]["recording_id"] == 1
        assert files_to_move[3]["id"] == 7
        assert files_to_move[4]["recording_id"] == -1
        assert files_to_move[4]["id"] == 9
        assert files_to_move[5]["recording_id"] == -1
        assert files_to_move[5]["id"] == 23
        assert files_to_move[8]["recording_id"] == -1
        assert files_to_move[8]["id"] == 29

    def test_recordings_to_move_query_max_bytes_and_age(self) -> None:
        """Test recordings_to_move_query using max_bytes + max_age."""
        max_age_timestamp = (self._now + datetime.timedelta(seconds=26)).timestamp()
        files_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        recordings_data = load_recordings(
            get_session=self._get_db_session,
            camera_identifier="test",
        )
        files_to_move = get_recordings_to_move(
            recordings_data=recordings_data,
            files_data=files_data,
            segment_length=5,
            max_bytes=110,
            min_age_timestamp=self._simulated_now.timestamp(),
            max_age_timestamp=max_age_timestamp,
            min_bytes=0,
            file_min_age_timestamp=self._simulated_now.timestamp(),
            drain=False,
        )

        assert len(files_to_move) == 13
        assert files_to_move[0]["recording_id"] == -1
        assert files_to_move[0]["id"] == 1
        assert files_to_move[1]["recording_id"] == 1
        assert files_to_move[1]["id"] == 3
        assert files_to_move[2]["recording_id"] == 1
        assert files_to_move[2]["id"] == 5
        assert files_to_move[3]["recording_id"] == 1
        assert files_to_move[3]["id"] == 7
        assert files_to_move[4]["recording_id"] == -1
        assert files_to_move[4]["id"] == 9
        assert files_to_move[5]["recording_id"] == 3
        assert files_to_move[5]["id"] == 11
        assert files_to_move[6]["recording_id"] == 3
        assert files_to_move[6]["id"] == 13
        assert files_to_move[7]["recording_id"] == 3
        assert files_to_move[7]["id"] == 15
        assert files_to_move[8]["recording_id"] == 3
        assert files_to_move[8]["id"] == 17
        assert files_to_move[9]["recording_id"] == -1
        assert files_to_move[9]["id"] == 23
        assert files_to_move[12]["recording_id"] == -1
        assert files_to_move[12]["id"] == 29

    def test_recordings_to_move_query_active_recording(self) -> None:
        """Test recordings_to_move_query where end_time is not set."""
        with self._get_db_session() as session:
            session.execute(
                update(Recordings).values(end_time=None).where(Recordings.id == 1)
            )
            session.commit()

        files_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        recordings_data = load_recordings(
            get_session=self._get_db_session,
            camera_identifier="test",
        )
        files_to_move = get_recordings_to_move(
            recordings_data=recordings_data,
            files_data=files_data,
            segment_length=5,
            max_bytes=80,
            min_age_timestamp=self._simulated_now.timestamp(),
            max_age_timestamp=0,
            min_bytes=0,
            file_min_age_timestamp=self._simulated_now.timestamp(),
            drain=False,
        )

        assert len(files_to_move) == 13

    def test_recordings_to_move_query_file_min_age_timestamp(self) -> None:
        """Test recordings_to_move_query using file_min_age_timestamp.

        Make sure that the file_min_age_timestamp is used to save the last few segments.
        """
        files_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        recordings_data = load_recordings(
            get_session=self._get_db_session,
            camera_identifier="test",
        )
        files_to_move = get_recordings_to_move(
            recordings_data=recordings_data,
            files_data=files_data,
            segment_length=5,
            max_bytes=1,
            min_age_timestamp=self._simulated_now.timestamp(),
            max_age_timestamp=0,
            min_bytes=0,
            file_min_age_timestamp=self._simulated_now.timestamp() - 35,
            drain=False,
        )

        assert len(files_to_move) == 8

    def test_recordings_to_move_query_drain(self) -> None:
        """Test recordings_to_move_query using drain."""
        files_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        recordings_data = load_recordings(
            get_session=self._get_db_session,
            camera_identifier="test",
        )
        files_to_move = get_recordings_to_move(
            recordings_data=recordings_data,
            files_data=files_data,
            segment_length=5,
            max_bytes=80,
            min_age_timestamp=self._simulated_now.timestamp(),
            max_age_timestamp=0,
            min_bytes=0,
            file_min_age_timestamp=self._simulated_now.timestamp(),
            drain=True,
        )

        assert len(files_to_move) == len(files_data)

    def test_recordings_to_move_query_drain_limit_not_reached(self) -> None:
        """Test recordings_to_move_query using drain when limit is not reached."""
        files_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        recordings_data = load_recordings(
            get_session=self._get_db_session,
            camera_identifier="test",
        )
        files_to_move = get_recordings_to_move(
            recordings_data=recordings_data,
            files_data=files_data,
            segment_length=5,
            max_bytes=9999,
            min_age_timestamp=self._simulated_now.timestamp(),
            max_age_timestamp=0,
            min_bytes=0,
            file_min_age_timestamp=self._simulated_now.timestamp(),
            drain=True,
        )

        assert len(files_to_move) == 6
        for file in files_to_move:
            assert file["recording_id"] == -1
