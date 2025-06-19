"""Tests for recorder."""
from __future__ import annotations

import datetime
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from viseron.components.storage.models import Files, Recordings
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.recorder import (
    AbstractRecorder,
    RecorderBase,
    Recording,
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
                start_time=datetime.datetime(
                    2023, 3, 1, 23, 30, tzinfo=datetime.timezone.utc
                ),  # 23:30 UTC March 1
                adjusted_start_time=datetime.datetime(
                    2023, 3, 1, 23, 30, tzinfo=datetime.timezone.utc
                ),
                end_time=datetime.datetime(
                    2023, 3, 2, 0, 30, tzinfo=datetime.timezone.utc
                ),  # 00:30 UTC March 2
                thumbnail_path="test",
            )
        )
        # Mid-day recording
        session.execute(
            insert(Recordings).values(
                camera_identifier="test1",
                start_time=datetime.datetime(
                    2023, 3, 2, 12, 0, tzinfo=datetime.timezone.utc
                ),  # 12:00 UTC March 2
                adjusted_start_time=datetime.datetime(
                    2023, 3, 2, 12, 0, tzinfo=datetime.timezone.utc
                ),
                end_time=datetime.datetime(
                    2023, 3, 2, 13, 0, tzinfo=datetime.timezone.utc
                ),  # 13:00 UTC March 2
                thumbnail_path="test",
            )
        )
        # Recording near day boundary
        session.execute(
            insert(Recordings).values(
                camera_identifier="test1",
                start_time=datetime.datetime(
                    2023, 3, 2, 22, 45, tzinfo=datetime.timezone.utc
                ),  # 22:45 UTC March 2
                adjusted_start_time=datetime.datetime(
                    2023, 3, 2, 22, 45, tzinfo=datetime.timezone.utc
                ),
                end_time=datetime.datetime(
                    2023, 3, 2, 23, 45, tzinfo=datetime.timezone.utc
                ),  # 23:45 UTC March 2
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
        result = recorder_base.delete_recording(
            datetime.timedelta(seconds=time.localtime().tm_gmtoff)
        )
        assert result is False

        mock_delete_recording.return_value = [
            MagicMock(spec=Recordings),
            MagicMock(spec=Recordings),
        ]
        result = recorder_base.delete_recording(
            datetime.timedelta(seconds=time.localtime().tm_gmtoff)
        )
        assert result is True


class ConcreteTestRecorder(AbstractRecorder):
    """Test recorder class that implements abstract methods."""

    def __init__(self, vis: Viseron, config, camera: AbstractCamera) -> None:
        super().__init__(vis, "test", config, camera)

    def _start(self, recording, shared_frame, objects_in_fov) -> None:
        pass

    def _stop(self, recording) -> None:
        pass

    @property
    def lookback(self) -> Literal[5]:
        """Return lookback."""
        return 5


@pytest.fixture(name="get_db_session_fragments")
def fixture_get_db_session_fragments(get_db_session: Callable[[], Session]):
    """Fixture to test fragments."""
    with get_db_session() as session:
        session.execute(
            insert(Recordings).values(
                camera_identifier="test1",
                start_time=datetime.datetime(
                    2023, 3, 1, 23, 30, tzinfo=datetime.timezone.utc
                ),  # 23:30 UTC March 1
                adjusted_start_time=datetime.datetime(
                    2023, 3, 1, 23, 30, tzinfo=datetime.timezone.utc
                ),
                end_time=datetime.datetime(
                    2023, 3, 2, 0, 30, tzinfo=datetime.timezone.utc
                ),  # 00:30 UTC March 2
                thumbnail_path="test",
            )
        )
        session.execute(
            insert(Files).values(
                # id=1,
                path="/tmp/fragment1.mp4",
                tier_id=1,
                tier_path="/tmp/tier1",
                camera_identifier="test1",
                category="recorder",
                subcategory="segments",
                duration=5.3,
                directory="/tmp",
                filename="fragment1.mp4",
                size=1024,
                orig_ctime=datetime.datetime(
                    2023, 3, 1, 23, 30, tzinfo=datetime.timezone.utc
                ),
            )
        )
        session.commit()
    yield get_db_session


@pytest.fixture(name="recorder")
def fixture_patched_recorder(vis: Viseron):
    """Fixture to create a test recorder with mocked vis.add_entity."""
    with patch.object(vis, "add_entity") as mock_add_entity:
        config = MagicMock()
        nested_dict = {"filename_pattern": "%H-%M-%S"}
        config.__getitem__.return_value.__getitem__.side_effect = nested_dict.get
        recorder = ConcreteTestRecorder(vis, config, MockCamera())
        # pylint: disable=protected-access
        recorder._logger = MagicMock()
        assert mock_add_entity.call_count == 2

        yield recorder


class TestAbstractRecorder:
    """Test the AbstractRecorder class."""

    def test_no_active_recording(self, recorder: ConcreteTestRecorder):
        """Test no active recording."""
        recording = None

        recorder.stop(recording)

        # pylint: disable=protected-access
        recorder._logger.error.assert_called_with(  # type: ignore [attr-defined]
            "No active recording to stop"
        )
        assert recorder.active_recording is None

    def test_concatenate_fragments_no_fragments(self, recorder: ConcreteTestRecorder):
        """Test _concatenate_fragments when no fragments are available."""
        start_time = datetime.datetime(2023, 3, 1, 12, 0, tzinfo=datetime.timezone.utc)
        recording = Recording(
            id=1,
            start_time=start_time,
            start_timestamp=start_time.timestamp(),
            end_time=None,
            end_timestamp=None,
            date="2023-03-01",
            thumbnail=None,
            thumbnail_path="/tmp/thumbnail.jpg",
            clip_path=None,
            objects=[],
        )

        # pylint: disable=protected-access
        recorder._concatenate_fragments(recording)

        # pylint: disable=protected-access
        recorder._logger.info.assert_called_with(  # type: ignore [attr-defined]
            "No fragments immediately available to generate event clip"
        )
        assert recording.clip_path is None

    def test_concatenate_fragments_with_fragments(
        self,
        recorder: ConcreteTestRecorder,
        get_db_session_fragments: Callable[[], Session],
    ):
        """Test _concatenate_fragments when fragments are available."""
        start_time = datetime.datetime(2023, 3, 1, 12, 0, tzinfo=datetime.timezone.utc)
        recording = Recording(
            id=1,
            start_time=start_time,
            start_timestamp=start_time.timestamp(),
            end_time=None,
            end_timestamp=None,
            date="2023-03-01",
            thumbnail=None,
            thumbnail_path="/tmp/thumbnail.jpg",
            clip_path=None,
            objects=[],
        )

        # pylint: disable=protected-access
        with patch.object(recorder._storage, "get_session") as mock_get_session, patch(
            "shutil.move"
        ) as mock_file_move:
            # Return a list of fragments from the database session
            mock_get_session.return_value = get_db_session_fragments()
            recorder._concatenate_fragments(recording)
            assert mock_file_move.call_count == 1

        assert recording.clip_path is not None
        (date, filename) = recording.clip_path.split("/")[-2:]
        assert date == recording.date
        assert filename == f"{recording.start_time.strftime('%H-%M-%S')}.mp4"
