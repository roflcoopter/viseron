"""Test the query functions."""

import datetime
from typing import Any
from unittest.mock import patch

import numpy as np
from croniter import croniter
from sqlalchemy import update

from viseron.components.storage.check_tier import (
    FILES_DTYPE,
    Worker,
    get_continuous_files_to_move,
    get_files_to_move,
    get_recordings_to_move,
    load_recordings,
    load_tier,
)
from viseron.components.storage.models import Recordings
from viseron.components.storage.storage_subprocess import DataItem
from viseron.const import CAMERA_SEGMENT_DURATION
from viseron.domains.camera.schedule import schedule_active

from tests.common import BaseTestWithRecordings

# Active for a single minute per year, so effectively never
NEVER_ACTIVE_SCHEDULE = [{"start": "0 0 1 1 *", "end": "1 0 1 1 *"}]
# Started every minute and ended once a year, so effectively always
ALWAYS_ACTIVE_SCHEDULE = [{"start": "* * * * *", "end": "0 0 1 1 *"}]


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
            file_min_age_timestamp=self._simulated_now.timestamp(),
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
            file_min_age_timestamp=self._simulated_now.timestamp(),
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
            file_min_age_timestamp=self._simulated_now.timestamp(),
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
            file_min_age_timestamp=self._simulated_now.timestamp(),
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
            file_min_age_timestamp=self._simulated_now.timestamp(),
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
            file_min_age_timestamp=self._simulated_now.timestamp(),
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
            file_min_age_timestamp=self._simulated_now.timestamp(),
            drain=True,
        )

        assert len(files_to_move) == 0

    def test_get_files_to_move_file_min_age(self) -> None:
        """Test get_files_to_move using file_min_age_timestamp.

        max_age alone would select 6 files, but file_min_age_timestamp is a hard
        floor on every selected file, keeping the 3 most recent of them. The age
        branch has no min-age guard of its own, so this is the only thing
        protecting files that are still being written to.
        """
        max_age_timestamp = (self._now + datetime.timedelta(seconds=26)).timestamp()
        file_min_age_timestamp = (
            self._now + datetime.timedelta(seconds=11)
        ).timestamp()
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
            file_min_age_timestamp=file_min_age_timestamp,
            drain=False,
        )

        assert list(files_to_move["id"]) == [1, 3, 5]

    def test_get_files_to_move_drain_ignores_file_min_age(self) -> None:
        """Test that drain bypasses file_min_age_timestamp.

        Mirrors get_recordings_to_move: a draining tier is being emptied, so the
        per-file floor does not apply.
        """
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
            file_min_age_timestamp=(self._now - datetime.timedelta(days=1)).timestamp(),
            drain=True,
        )

        assert len(files_to_move) == len(data)

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


class TestGetContinuousFilesToMove:
    """Test get_continuous_files_to_move: schedule-aware continuous retention."""

    # 08:00-18:00 daily
    SCHEDULE = [{"start": "0 8 * * *", "end": "0 18 * * *"}]

    def _files(self, *entries: tuple[int, int, datetime.datetime]) -> np.ndarray:
        return np.array(
            [
                (id_, size, int(ts.timestamp()), f"/test/{id_}.m4s", "/test/")
                for id_, size, ts in entries
            ],
            dtype=FILES_DTYPE,
        )

    def test_no_schedule_matches_get_files_to_move(self) -> None:
        """With schedule_entries=None, behaves exactly like get_files_to_move."""
        now = datetime.datetime(2024, 1, 2, 20, 0, tzinfo=datetime.timezone.utc)
        data = self._files(
            (1, 10, now - datetime.timedelta(days=40)),
            (2, 10, now - datetime.timedelta(seconds=5)),
        )
        max_age_timestamp = (now - datetime.timedelta(days=30)).timestamp()

        result = get_continuous_files_to_move(
            data=data.copy(),
            max_bytes=0,
            min_age_timestamp=now.timestamp(),
            min_bytes=0,
            max_age_timestamp=max_age_timestamp,
            file_min_age_timestamp=now.timestamp(),
            drain=False,
            now=now,
            schedule_entries=None,
            timezone="UTC",
            lookback_seconds=30,
        )
        expected = get_files_to_move(
            data=data.copy(),
            max_bytes=0,
            min_age_timestamp=now.timestamp(),
            min_bytes=0,
            max_age_timestamp=max_age_timestamp,
            file_min_age_timestamp=now.timestamp(),
            drain=False,
        )
        assert list(result["id"]) == list(expected["id"])

    def test_file_recorded_during_active_window_keeps_full_retention(self) -> None:
        """A file recorded while the schedule was active is not evicted early.

        Case:
        - Recorded at 10:00 (inside 08:00-18:00 schedule)
        - Now is 20:00 the same day, ten hours after recording
        - Max age is 30 days

        Result: file is not evicted, because it was recorded during an active window
        and is nowhere near the max age.
        """
        now = datetime.datetime(2024, 1, 2, 20, 0, tzinfo=datetime.timezone.utc)
        recorded_at = datetime.datetime(2024, 1, 2, 10, 0, tzinfo=datetime.timezone.utc)
        data = self._files((1, 10, recorded_at))

        result = get_continuous_files_to_move(
            data=data,
            max_bytes=0,
            min_age_timestamp=now.timestamp(),
            min_bytes=0,
            max_age_timestamp=(now - datetime.timedelta(days=30)).timestamp(),
            file_min_age_timestamp=now.timestamp(),
            drain=False,
            now=now,
            schedule_entries=self.SCHEDULE,
            timezone="UTC",
            lookback_seconds=30,
        )
        assert len(result) == 0

    def test_file_recorded_during_inactive_window_evicted_past_lookback(
        self,
    ) -> None:
        """A file recorded while the schedule was inactive is capped to lookback.

        Case:
        - Schedule is 08:00-18:00 daily
        - Recorded at 19:00 (after the 18:00 end)
        - Now is 20:00, one hour later - well past the 30s lookback
        - Max age is 30 days

        Result: file is evicted, because it was recorded during an inactive window
        and is now past the lookback threshold.
        """
        now = datetime.datetime(2024, 1, 2, 20, 0, tzinfo=datetime.timezone.utc)
        recorded_at = datetime.datetime(2024, 1, 2, 19, 0, tzinfo=datetime.timezone.utc)
        data = self._files((1, 10, recorded_at))

        result = get_continuous_files_to_move(
            data=data,
            max_bytes=0,
            min_age_timestamp=now.timestamp(),
            min_bytes=0,
            max_age_timestamp=(now - datetime.timedelta(days=30)).timestamp(),
            file_min_age_timestamp=now.timestamp(),
            drain=False,
            now=now,
            schedule_entries=self.SCHEDULE,
            timezone="UTC",
            lookback_seconds=30,
        )
        assert list(result["id"]) == [1]

    def test_file_recorded_during_inactive_window_within_lookback_is_kept(
        self,
    ) -> None:
        """A file inside the lookback buffer is never evicted.

        Even though it was recorded while the schedule was inactive, it may
        still be needed as lookback for the next event.
        """
        now = datetime.datetime(2024, 1, 2, 20, 0, tzinfo=datetime.timezone.utc)
        recorded_at = now - datetime.timedelta(seconds=10)  # 19:59:50, inactive
        data = self._files((1, 10, recorded_at))

        result = get_continuous_files_to_move(
            data=data,
            max_bytes=0,
            min_age_timestamp=now.timestamp(),
            min_bytes=0,
            max_age_timestamp=(now - datetime.timedelta(days=30)).timestamp(),
            file_min_age_timestamp=now.timestamp(),
            drain=False,
            now=now,
            schedule_entries=self.SCHEDULE,
            timezone="UTC",
            lookback_seconds=30,
        )
        assert len(result) == 0

    def test_inactive_file_straddling_lookback_boundary_is_kept(self) -> None:
        """The segment covering the start of the pre-roll window is retained."""
        now = datetime.datetime(2024, 1, 2, 20, 0, tzinfo=datetime.timezone.utc)
        # Inactive (20:00 is outside 08:00-18:00), one second older than the
        # lookback window, so it is the segment straddling its start.
        recorded_at = now - datetime.timedelta(seconds=31)
        data = self._files((1, 10, recorded_at))

        result = get_continuous_files_to_move(
            data=data,
            max_bytes=0,
            min_age_timestamp=now.timestamp(),
            min_bytes=0,
            max_age_timestamp=(now - datetime.timedelta(days=30)).timestamp(),
            file_min_age_timestamp=now.timestamp(),
            drain=False,
            now=now,
            schedule_entries=self.SCHEDULE,
            timezone="UTC",
            lookback_seconds=30,
        )
        assert len(result) == 0

    def test_inactive_files_respect_min_age(self) -> None:
        """A configured min_age is never overridden by the schedule cutoff.

        The shortened inactive horizon selects the file, but the per-file floor
        the caller passes still keeps it, exactly as it would for an active file.
        """
        now = datetime.datetime(2024, 1, 2, 20, 0, tzinfo=datetime.timezone.utc)
        recorded_at = now - datetime.timedelta(minutes=10)  # inactive
        data = self._files((1, 10, recorded_at))

        result = get_continuous_files_to_move(
            data=data,
            max_bytes=0,
            # min_age of one hour, i.e. nothing younger than this may be moved.
            min_age_timestamp=(now - datetime.timedelta(hours=1)).timestamp(),
            min_bytes=0,
            max_age_timestamp=(now - datetime.timedelta(days=30)).timestamp(),
            file_min_age_timestamp=(now - datetime.timedelta(hours=1)).timestamp(),
            drain=False,
            now=now,
            schedule_entries=self.SCHEDULE,
            timezone="UTC",
            lookback_seconds=30,
        )
        assert len(result) == 0

    def test_respects_configured_timezone(self) -> None:
        """The configured timezone (not UTC) decides whether the window was active."""
        now = datetime.datetime(2024, 1, 2, 20, 0, tzinfo=datetime.timezone.utc)
        recorded_at = datetime.datetime(2024, 1, 2, 7, 30, tzinfo=datetime.timezone.utc)
        data = self._files((1, 10, recorded_at))
        max_age_timestamp = (now - datetime.timedelta(days=30)).timestamp()

        result_utc = get_continuous_files_to_move(
            data=data.copy(),
            max_bytes=0,
            min_age_timestamp=now.timestamp(),
            min_bytes=0,
            max_age_timestamp=max_age_timestamp,
            file_min_age_timestamp=now.timestamp(),
            drain=False,
            now=now,
            schedule_entries=self.SCHEDULE,
            timezone="UTC",
            lookback_seconds=30,
        )
        assert list(result_utc["id"]) == [1]

        result_stockholm = get_continuous_files_to_move(
            data=data.copy(),
            max_bytes=0,
            min_age_timestamp=now.timestamp(),
            min_bytes=0,
            max_age_timestamp=max_age_timestamp,
            file_min_age_timestamp=now.timestamp(),
            drain=False,
            now=now,
            schedule_entries=self.SCHEDULE,
            timezone="Europe/Stockholm",
            lookback_seconds=30,
        )
        assert len(result_stockholm) == 0

    def test_mixed_active_and_inactive_files(self) -> None:
        """Active and inactive files are evaluated independently in one call."""
        now = datetime.datetime(2024, 1, 2, 20, 0, tzinfo=datetime.timezone.utc)
        active_recorded = datetime.datetime(
            2024, 1, 2, 10, 0, tzinfo=datetime.timezone.utc
        )
        inactive_recorded = datetime.datetime(
            2024, 1, 2, 19, 0, tzinfo=datetime.timezone.utc
        )
        data = self._files(
            (1, 10, active_recorded),
            (2, 10, inactive_recorded),
        )

        result = get_continuous_files_to_move(
            data=data,
            max_bytes=0,
            min_age_timestamp=now.timestamp(),
            min_bytes=0,
            max_age_timestamp=(now - datetime.timedelta(days=30)).timestamp(),
            file_min_age_timestamp=now.timestamp(),
            drain=False,
            now=now,
            schedule_entries=self.SCHEDULE,
            timezone="UTC",
            lookback_seconds=30,
        )
        assert list(result["id"]) == [2]

    def test_schedule_evaluation_does_not_scale_with_file_count(self) -> None:
        """Cron is parsed per schedule transition, not per file.

        A tier holding a couple of days of segments has thousands of rows, and
        evaluating the schedule for each of them parses two cron expressions per
        entry. The state only flips where a cron fires, so the whole range is
        resolved from a handful of evaluations.
        """
        now = datetime.datetime(2024, 1, 3, 4, 0, tzinfo=datetime.timezone.utc)
        oldest = now - datetime.timedelta(days=2)
        data = self._files(
            *[
                (id_, 10, oldest + datetime.timedelta(seconds=120 * id_))
                for id_ in range(1, 1500)
            ]
        )
        lookback_seconds = 30

        with patch(
            "viseron.domains.camera.schedule.croniter", wraps=croniter
        ) as mock_croniter:
            result = get_continuous_files_to_move(
                data=data,
                max_bytes=0,
                min_age_timestamp=now.timestamp(),
                min_bytes=0,
                max_age_timestamp=0,
                file_min_age_timestamp=now.timestamp(),
                drain=False,
                now=now,
                schedule_entries=self.SCHEDULE,
                timezone="UTC",
                lookback_seconds=lookback_seconds,
            )

        # 6 window edges across the two days, plus the initial state
        assert mock_croniter.call_count < 50

        cutoff = (
            now - datetime.timedelta(seconds=lookback_seconds + CAMERA_SEGMENT_DURATION)
        ).timestamp()
        expected = {
            int(row["id"])
            for row in data
            if row["orig_ctime"] < cutoff
            and not schedule_active(
                self.SCHEDULE,
                "UTC",
                datetime.datetime.fromtimestamp(
                    int(row["orig_ctime"]), tz=datetime.timezone.utc
                ),
            )
        }
        assert expected
        assert set(result["id"].tolist()) == expected


class TestShouldCheckTierFiles(BaseTestWithRecordings):
    """Test Worker._should_check_tier_files fast-path gate for file checks."""

    def _make_item(self, **kwargs: Any) -> DataItem:
        """Return a DataItem with sensible defaults."""
        defaults: dict = {
            "cmd": "check_tier",
            "camera_identifier": "test",
            "tier_id": 0,
            "category": "recorder",
            "subcategories": ["segments"],
            "throttle_period": datetime.timedelta(seconds=0),
            "max_bytes": 0,
            "min_age": datetime.timedelta(seconds=0),
            "max_age": datetime.timedelta(seconds=0),
            "min_bytes": 0,
            "drain": False,
            "files_enabled": True,
            "events_enabled": False,
        }
        defaults.update(kwargs)
        return DataItem(**defaults)

    def _make_worker(self) -> Worker:
        """Return a Worker wired to the test DB session."""
        worker = Worker.__new__(Worker)
        worker._get_session = self._get_db_session
        worker._last_call = {}
        worker._check_locks = {}
        worker._checks_in_progress = {}
        return worker

    def test_files_disabled_returns_false(self) -> None:
        """files_enabled=False must return False."""
        worker = self._make_worker()
        item = self._make_item(files_enabled=False, max_bytes=100)
        assert worker._should_check_tier_files(item) is False

    def test_empty_tier_returns_false(self) -> None:
        """Return False when no files exist for the given camera/tier/category."""
        worker = self._make_worker()
        item = self._make_item(camera_identifier="nonexistent", max_bytes=10)
        assert worker._should_check_tier_files(item) is False

    def test_wrong_subcategory_returns_false(self) -> None:
        """Return False when subcategory has no files."""
        worker = self._make_worker()
        item = self._make_item(subcategories=["event_clips"], max_bytes=10)
        assert worker._should_check_tier_files(item) is False

    def test_wrong_tier_id_returns_false(self) -> None:
        """Return False when tier_id has no files."""
        worker = self._make_worker()
        item = self._make_item(tier_id=99, max_bytes=10)
        assert worker._should_check_tier_files(item) is False

    def test_max_bytes_exceeded_returns_true(self) -> None:
        """Return True when total size (150) exceeds max_bytes."""
        worker = self._make_worker()
        item = self._make_item(max_bytes=100)
        assert worker._should_check_tier_files(item) is True

    def test_max_bytes_exact_boundary_returns_true(self) -> None:
        """Return True when total size equals max_bytes (>= threshold)."""
        worker = self._make_worker()
        item = self._make_item(max_bytes=150)
        assert worker._should_check_tier_files(item) is True

    def test_max_bytes_not_exceeded_returns_false(self) -> None:
        """Return False when total size (150) is below max_bytes."""
        worker = self._make_worker()
        item = self._make_item(max_bytes=200)
        assert worker._should_check_tier_files(item) is False

    def test_max_bytes_zero_skips_bytes_check_returns_false(self) -> None:
        """max_bytes=0 disables the bytes gate."""
        worker = self._make_worker()
        item = self._make_item(max_bytes=0, max_age=datetime.timedelta(0))
        assert worker._should_check_tier_files(item) is False

    def test_max_age_exceeded_returns_true(self) -> None:
        """Return True when oldest file exceeds max_age and total_size >= min_bytes.

        Oldest file orig_ctime = _now. We mock utcnow() to return
        _now + 2h so that oldest_ctime < (now - 1h) is satisfied.
        min_bytes defaults to 0, so total_size >= 0 passes.
        """
        worker = self._make_worker()
        item = self._make_item(max_age=datetime.timedelta(hours=1))
        future_now = self._now + datetime.timedelta(hours=2)
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=future_now
        ):
            assert worker._should_check_tier_files(item) is True

    def test_max_age_exceeded_but_min_bytes_not_reached_returns_false(self) -> None:
        """Return False when max_age is exceeded but total_size is below min_bytes."""
        worker = self._make_worker()
        item = self._make_item(
            max_age=datetime.timedelta(hours=1),
            min_bytes=9999,
        )
        future_now = self._now + datetime.timedelta(hours=2)
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=future_now
        ):
            assert worker._should_check_tier_files(item) is False

    def test_max_age_not_exceeded_returns_false(self) -> None:
        """Return False when oldest file is newer than max_age."""
        worker = self._make_worker()
        # Files are freshly inserted; 365 days max_age will never be exceeded.
        item = self._make_item(max_age=datetime.timedelta(days=365))
        assert worker._should_check_tier_files(item) is False

    def test_max_age_zero_skips_age_check_returns_false(self) -> None:
        """max_age=timedelta(0) disables the age gate.

        Combined with max_bytes=0, the check returns False.
        """
        worker = self._make_worker()
        item = self._make_item(max_bytes=0, max_age=datetime.timedelta(0))
        future_now = self._now + datetime.timedelta(hours=24)
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=future_now
        ):
            assert worker._should_check_tier_files(item) is False

    def test_both_gates_bytes_triggers(self) -> None:
        """Return True via bytes gate even when age gate would not fire."""
        worker = self._make_worker()
        item = self._make_item(
            max_bytes=100,
            max_age=datetime.timedelta(days=365),
        )
        assert worker._should_check_tier_files(item) is True

    def test_both_gates_age_triggers(self) -> None:
        """Return True via age gate even when bytes gate would not fire."""
        worker = self._make_worker()
        item = self._make_item(
            max_bytes=9999,
            max_age=datetime.timedelta(hours=1),
        )
        future_now = self._now + datetime.timedelta(hours=2)
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=future_now
        ):
            assert worker._should_check_tier_files(item) is True

    def test_both_gates_neither_triggers_returns_false(self) -> None:
        """Return False when neither bytes nor age gate fires."""
        worker = self._make_worker()
        item = self._make_item(
            max_bytes=9999,
            max_age=datetime.timedelta(days=365),
        )
        assert worker._should_check_tier_files(item) is False

    def test_continuous_schedule_inactive_file_past_lookback_returns_true(self) -> None:
        """A schedule-aware lookback gate fires even when bytes/age gates would not.

        Without the schedule-aware gate, an inactive-window file older than the
        lookback buffer would never trigger a real check (and would sit forever)
        since neither max_bytes nor max_age alone would notice it.
        """
        worker = self._make_worker()
        item = self._make_item(
            max_bytes=0,
            max_age=datetime.timedelta(days=365),
            continuous_schedule=NEVER_ACTIVE_SCHEDULE,
            continuous_schedule_timezone="UTC",
            continuous_lookback_seconds=1,
        )
        future_now = self._now + datetime.timedelta(minutes=10)
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=future_now
        ):
            assert worker._should_check_tier_files(item) is True

    def test_continuous_schedule_oldest_file_within_lookback_returns_false(
        self,
    ) -> None:
        """No gate fires when the oldest file is still within the lookback buffer."""
        worker = self._make_worker()
        item = self._make_item(
            max_bytes=0,
            max_age=datetime.timedelta(days=365),
            continuous_schedule=NEVER_ACTIVE_SCHEDULE,
            continuous_schedule_timezone="UTC",
            continuous_lookback_seconds=99999,
        )
        assert worker._should_check_tier_files(item) is False

    def test_continuous_schedule_only_active_files_returns_false(self) -> None:
        """Files recorded while the schedule was active do not fire the gate.

        They keep the full configured retention, so the schedule has nothing to
        contribute and the expensive check is skipped. Without this the gate is
        defeated for every camera that configures a schedule, since a tier almost
        always holds files older than the lookback buffer.
        """
        worker = self._make_worker()
        item = self._make_item(
            max_bytes=0,
            max_age=datetime.timedelta(days=365),
            continuous_schedule=ALWAYS_ACTIVE_SCHEDULE,
            continuous_schedule_timezone="UTC",
            continuous_lookback_seconds=1,
        )
        future_now = self._now + datetime.timedelta(minutes=10)
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=future_now
        ):
            assert worker._should_check_tier_files(item) is False

    def test_continuous_schedule_inactive_file_newer_than_oldest_returns_true(
        self,
    ) -> None:
        """The gate looks at every inactive window, not just the oldest file.

        The oldest file was recorded while the schedule was active, but a later
        one was not, so there is still something for the schedule to evict.
        """
        # Schedule ends on the next whole minute, which the last files fall after
        ends_at = (self._now + datetime.timedelta(minutes=1)).replace(
            second=0, microsecond=0
        )
        worker = self._make_worker()
        item = self._make_item(
            max_bytes=0,
            max_age=datetime.timedelta(days=365),
            continuous_schedule=[
                {
                    "start": "* * * * *",
                    "end": f"{ends_at.minute} {ends_at.hour} "
                    f"{ends_at.day} {ends_at.month} *",
                }
            ],
            continuous_schedule_timezone="UTC",
            continuous_lookback_seconds=1,
        )
        future_now = self._now + datetime.timedelta(minutes=10)
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=future_now
        ):
            assert worker._should_check_tier_files(item) is True

    def test_continuous_schedule_too_many_windows_returns_true(self) -> None:
        """A schedule with more windows than can be queried defers to the check.

        Every file here was recorded while the schedule was active, so the exact
        answer is False, but the windows are capped before that can be decided.
        """
        # Schedule ends after the last file, so no file is in an inactive window
        ends_at = (self._now + datetime.timedelta(minutes=3)).replace(
            second=0, microsecond=0
        )
        worker = self._make_worker()
        item = self._make_item(
            max_bytes=0,
            max_age=datetime.timedelta(days=365),
            continuous_schedule=[
                {
                    "start": "* * * * *",
                    "end": f"{ends_at.minute} {ends_at.hour} "
                    f"{ends_at.day} {ends_at.month} *",
                }
            ],
            continuous_schedule_timezone="UTC",
            continuous_lookback_seconds=1,
        )
        future_now = self._now + datetime.timedelta(minutes=10)
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=future_now
        ):
            assert worker._should_check_tier_files(item) is False
            with patch("viseron.components.storage.check_tier.MAX_SCHEDULE_CHANGES", 2):
                assert worker._should_check_tier_files(item) is True


class TestCheckTierIntegration(BaseTestWithRecordings):
    """Integration tests for Worker.check_tier through the full gate + logic pipeline.

    These tests verify that the fast-path gate (_should_check_tier_files inside
    check_tier_files) correctly controls whether the heavy numpy logic executes,
    and that when the gate passes the results match the standalone functions.
    """

    def _make_item(self, **kwargs: Any) -> DataItem:
        """Return a DataItem with sensible defaults."""
        defaults: dict = {
            "cmd": "check_tier",
            "camera_identifier": "test",
            "tier_id": 0,
            "category": "recorder",
            "subcategories": ["segments"],
            "throttle_period": datetime.timedelta(seconds=0),
            "max_bytes": 0,
            "min_age": datetime.timedelta(seconds=0),
            "max_age": datetime.timedelta(seconds=0),
            "min_bytes": 0,
            "drain": False,
            "files_enabled": True,
            "events_enabled": False,
        }
        defaults.update(kwargs)
        return DataItem(**defaults)

    def _make_worker(self) -> Worker:
        """Return a Worker wired to the test DB session."""
        worker = Worker.__new__(Worker)
        worker._get_session = self._get_db_session
        worker._last_call = {}
        worker._check_locks = {}
        worker._checks_in_progress = {}
        return worker

    def test_integration_max_bytes_exceeded(self) -> None:
        """Gate passes and check_tier_files produces results when max_bytes exceeded."""
        worker = self._make_worker()
        # Mock utcnow so the min_age filter inside check_tier_files includes all files
        mock_now = self._simulated_now + datetime.timedelta(minutes=10)
        item = self._make_item(
            max_bytes=100,
            min_age=datetime.timedelta(seconds=1),
        )
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=mock_now
        ):
            worker.check_tier(item)

        assert item.data is not None
        assert len(item.data) > 0
        # Verify expected dtype fields from stripped result
        assert "id" in item.data.dtype.names
        assert "path" in item.data.dtype.names
        assert "tier_path" in item.data.dtype.names

    def test_integration_max_age_exceeded(self) -> None:
        """Gate passes and check_tier_files produces results when max_age exceeded."""
        worker = self._make_worker()
        item = self._make_item(
            max_age=datetime.timedelta(hours=1),
            min_age=datetime.timedelta(seconds=1),
        )
        # Mock now so oldest file exceeds 1h age
        future_now = self._now + datetime.timedelta(hours=2)
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=future_now
        ):
            worker.check_tier(item)

        assert item.data is not None
        assert len(item.data) > 0
        assert "id" in item.data.dtype.names

    def test_integration_drain_limit_reached(self) -> None:
        """Gate passes with all files returned when drain=True and limit exceeded."""
        worker = self._make_worker()
        mock_now = self._simulated_now + datetime.timedelta(minutes=10)
        item = self._make_item(
            max_bytes=80,
            min_age=datetime.timedelta(seconds=1),
            drain=True,
        )
        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=mock_now
        ):
            worker.check_tier(item)

        assert item.data is not None
        assert len(item.data) == 15
        assert "id" in item.data.dtype.names

    def test_integration_max_bytes_not_exceeded(self) -> None:
        """Gate blocks when max_bytes not exceeded, returns empty array."""
        worker = self._make_worker()
        item = self._make_item(max_bytes=9999)
        worker.check_tier(item)

        assert item.data is not None
        assert item.data.size == 0

    def test_integration_max_age_not_exceeded(self) -> None:
        """Gate blocks when max_age not exceeded, returns empty array."""
        worker = self._make_worker()
        item = self._make_item(max_age=datetime.timedelta(days=365))
        worker.check_tier(item)

        assert item.data is not None
        assert item.data.size == 0

    def test_integration_drain_limit_not_reached(self) -> None:
        """Gate blocks when drain=True but no limits exceeded."""
        worker = self._make_worker()
        item = self._make_item(max_bytes=9999, drain=True)
        worker.check_tier(item)

        assert item.data is not None
        assert item.data.size == 0

    def test_integration_result_matches_standalone_max_bytes(self) -> None:
        """Full pipeline produces same file IDs as standalone get_files_to_move."""
        worker = self._make_worker()
        # Use a fixed mock now so min_age_timestamp is deterministic
        mock_now = self._now + datetime.timedelta(seconds=200)
        item = self._make_item(
            max_bytes=100,
            min_age=datetime.timedelta(seconds=10),
        )

        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=mock_now
        ):
            worker.check_tier(item)

        # Compute expected via standalone path with same params
        expected_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        # Replicate what check_tier_files computes internally
        min_age_timestamp = (mock_now - datetime.timedelta(seconds=10)).timestamp()
        expected = get_files_to_move(
            data=expected_data,
            max_bytes=100,
            min_age_timestamp=min_age_timestamp,
            min_bytes=0,
            max_age_timestamp=0,
            file_min_age_timestamp=min_age_timestamp,
            drain=False,
        )

        assert item.data is not None
        assert len(item.data) == len(expected)
        assert list(item.data["id"]) == list(expected["id"])

    def test_integration_result_matches_standalone_drain(self) -> None:
        """Full pipeline drain returns same file IDs as standalone get_files_to_move."""
        worker = self._make_worker()
        mock_now = self._now + datetime.timedelta(seconds=200)
        item = self._make_item(
            max_bytes=80,
            min_age=datetime.timedelta(seconds=10),
            drain=True,
        )

        with patch(
            "viseron.components.storage.check_tier.utcnow", return_value=mock_now
        ):
            worker.check_tier(item)

        expected_data = load_tier(
            get_session=self._get_db_session,
            category="recorder",
            subcategories=["segments"],
            tier_id=0,
            camera_identifier="test",
        )
        min_age_timestamp = (mock_now - datetime.timedelta(seconds=10)).timestamp()
        expected = get_files_to_move(
            data=expected_data,
            max_bytes=80,
            min_age_timestamp=min_age_timestamp,
            min_bytes=0,
            max_age_timestamp=0,
            file_min_age_timestamp=min_age_timestamp,
            drain=True,
        )

        assert item.data is not None
        assert len(item.data) == len(expected)
        assert list(item.data["id"]) == list(expected["id"])
