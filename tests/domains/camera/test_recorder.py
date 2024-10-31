"""Tests for recorder."""
from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from viseron.components.storage.models import Recordings
from viseron.domains.camera.recorder import (
    RecorderBase,
    delete_recordings,
    get_recordings,
)

from tests.common import MockCamera

if TYPE_CHECKING:
    from viseron import Viseron


@pytest.fixture(scope="function")
def get_db_session_recordings(get_db_session: Callable[[], Session]):
    """Fixture to test recordings with timezone edge cases."""
    with get_db_session() as session:
        # Create recordings across midnight UTC to test timezone handling
        session.execute(
            insert(Recordings).values(
                camera_identifier="test1",
                start_time=datetime.datetime(2023, 3, 1, 23, 30),  # 23:30 UTC March 1
                adjusted_start_time=datetime.datetime(2023, 3, 1, 23, 30),
                end_time=datetime.datetime(2023, 3, 2, 0, 30),  # 00:30 UTC March 2
                thumbnail_path="test",
            )
        )
        # Mid-day recording
        session.execute(
            insert(Recordings).values(
                camera_identifier="test1",
                start_time=datetime.datetime(2023, 3, 2, 12, 0),  # 12:00 UTC March 2
                adjusted_start_time=datetime.datetime(2023, 3, 2, 12, 0),
                end_time=datetime.datetime(2023, 3, 2, 13, 0),  # 13:00 UTC March 2
                thumbnail_path="test",
            )
        )
        # Recording near day boundary
        session.execute(
            insert(Recordings).values(
                camera_identifier="test1",
                start_time=datetime.datetime(2023, 3, 2, 22, 45),  # 22:45 UTC March 2
                adjusted_start_time=datetime.datetime(2023, 3, 2, 22, 45),
                end_time=datetime.datetime(2023, 3, 2, 23, 45),  # 23:45 UTC March 2
                thumbnail_path="test",
            )
        )
        session.commit()
    yield get_db_session


def test_get_recordings_utc(get_db_session_recordings: Callable[[], Session]) -> None:
    """Test get_recordings in UTC."""
    recordings = get_recordings(
        get_db_session_recordings, "test1", utc_offset=datetime.timedelta(hours=0)
    )
    assert len(recordings) == 2  # March 1 and 2
    assert "2023-03-01" in recordings
    assert "2023-03-02" in recordings
    assert len(recordings["2023-03-02"]) == 2  # Two recordings on March 2 UTC


def test_get_recordings_positive_offset(
    get_db_session_recordings: Callable[[], Session]
) -> None:
    """Test get_recordings in UTC+5:30 (India)."""
    recordings = get_recordings(
        get_db_session_recordings,
        "test1",
        utc_offset=datetime.timedelta(hours=5, minutes=30),
    )
    # The 23:30 UTC March 1 recording should appear as 05:00 March 2 local time
    assert "2023-03-02" in recordings
    assert len(recordings["2023-03-02"]) == 2
    assert "2023-03-03" in recordings
    assert len(recordings["2023-03-03"]) == 1


def test_get_recordings_negative_offset(
    get_db_session_recordings: Callable[[], Session]
) -> None:
    """Test get_recordings in UTC-5 (Eastern)."""
    recordings = get_recordings(
        get_db_session_recordings, "test1", utc_offset=datetime.timedelta(hours=-5)
    )
    # The 23:30 UTC March 1 recording should appear as 18:30 March 1 local time
    assert "2023-03-01" in recordings
    assert len(recordings["2023-03-01"]) == 1


def test_get_recordings_date_specific_timezone(
    get_db_session_recordings: Callable[[], Session]
) -> None:
    """Test get_recordings with specific date in different timezone."""
    # Test in UTC+1
    recordings = get_recordings(
        get_db_session_recordings,
        "test1",
        utc_offset=datetime.timedelta(hours=1),
        date="2023-03-02",
    )
    # Should include recordings from 00:00 to 23:59 local time on March 2
    assert len(recordings) == 1
    assert "2023-03-02" in recordings

    # The 22:45 UTC recording should be 23:45 local time and still included
    recording_times = [rec["start_time"] for rec in recordings["2023-03-02"].values()]
    assert (
        datetime.datetime(2023, 3, 2, 22, 45, tzinfo=datetime.timezone.utc)
        in recording_times
    )


def test_get_recordings_latest_with_timezone(
    get_db_session_recordings: Callable[[], Session]
) -> None:
    """Test get_recordings latest flag with timezone consideration."""
    # Test in UTC-7 (PDT)
    recordings = get_recordings(
        get_db_session_recordings,
        "test1",
        utc_offset=datetime.timedelta(hours=-7),
        latest=True,
    )
    assert len(recordings) == 1
    # Latest recording (22:45 UTC) should appear as 15:45 local time
    latest_date = list(recordings.keys())[0]
    latest_recording = list(recordings[latest_date].values())[0]
    assert latest_recording["start_time"] == datetime.datetime(
        2023, 3, 2, 22, 45, tzinfo=datetime.timezone.utc
    )


def test_get_recordings_latest_daily_with_timezone(
    get_db_session_recordings: Callable[[], Session]
) -> None:
    """Test get_recordings latest daily flag with timezone consideration."""
    # Test in UTC+9 (Japan)
    recordings = get_recordings(
        get_db_session_recordings,
        "test1",
        utc_offset=datetime.timedelta(hours=9),
        latest=True,
        daily=True,
    )
    # Should get the latest recording for each day in the local timezone
    assert len(recordings) >= 1
    for _date, date_recordings in recordings.items():
        assert len(date_recordings) == 1  # Only one (latest) recording per day


def test_delete_recordings_with_timezone(
    get_db_session_recordings: Callable[[], Session]
) -> None:
    """Test delete_recordings with timezone consideration."""
    # Test deleting recordings for a specific date in UTC+1
    recordings = delete_recordings(
        get_db_session_recordings,
        "test1",
        date="2023-03-02",
        utc_offset=datetime.timedelta(hours=1),
    )
    # Should delete all recordings that fall within March 2 in UTC+1
    assert len(recordings) >= 1
    for recording in recordings:
        # Convert UTC time to local time and verify it falls within the specified date
        local_time = recording.start_time + datetime.timedelta(hours=1)
        assert local_time.date() == datetime.date(2023, 3, 2)


class Recorder(RecorderBase):
    """Recorder class."""

    @property
    def lookback(self) -> Literal[5]:
        """Return lookback."""
        return 5


class TestRecorderBase:
    """Test the RecorderBase class."""

    @patch("viseron.domains.camera.recorder.delete_recordings")
    def test_delete_recording(
        self,
        mock_delete_recording: Mock,
        vis: Viseron,
    ):
        """Test delete_recording."""
        mock_delete_recording.return_value = []
        recorder_base = Recorder(vis, MagicMock(), MockCamera())
        result = recorder_base.delete_recording()
        assert result is False

        mock_delete_recording.return_value = [
            MagicMock(spec=Recordings),
            MagicMock(spec=Recordings),
        ]
        result = recorder_base.delete_recording()
        assert result is True
