"""Tests for recorder."""
from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import TYPE_CHECKING
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
    """Fixture to test recordings."""
    with get_db_session() as session:
        for i in range(1, 2):
            session.execute(
                insert(Recordings).values(
                    camera_identifier=f"test{i}",
                    start_time=datetime.datetime(2023, 3, 1, 12, 0),
                    end_time=datetime.datetime(2023, 3, 1, 12, 3),
                    thumbnail_path="test",
                )
            )
            session.execute(
                insert(Recordings).values(
                    camera_identifier=f"test{i}",
                    start_time=datetime.datetime(2023, 3, 1, 12, 10),
                    end_time=datetime.datetime(2023, 3, 1, 12, 12),
                    thumbnail_path="test",
                )
            )
            session.execute(
                insert(Recordings).values(
                    camera_identifier=f"test{i}",
                    start_time=datetime.datetime(2023, 3, 2, 12, 0),
                    end_time=datetime.datetime(2023, 3, 2, 12, 3),
                    thumbnail_path="test",
                )
            )
            session.execute(
                insert(Recordings).values(
                    camera_identifier=f"test{i}",
                    start_time=datetime.datetime(2023, 3, 2, 12, 10),
                    end_time=datetime.datetime(2023, 3, 2, 12, 12),
                    thumbnail_path="test",
                )
            )
            session.execute(
                insert(Recordings).values(
                    camera_identifier=f"test{i}",
                    start_time=datetime.datetime(2023, 3, 3, 12, 0),
                    end_time=datetime.datetime(2023, 3, 3, 12, 3),
                    thumbnail_path="test",
                )
            )
            session.execute(
                insert(Recordings).values(
                    camera_identifier=f"test{i}",
                    start_time=datetime.datetime(2023, 3, 3, 12, 10),
                    end_time=datetime.datetime(2023, 3, 3, 12, 12),
                    thumbnail_path="test",
                )
            )
        session.commit()
    yield get_db_session


def test_get_recordings(get_db_session_recordings: Callable[[], Session]) -> None:
    """Test get_recording."""
    recordings = get_recordings(get_db_session_recordings, "test1")
    assert len(recordings.items()) == 3
    assert len(recordings.items()) == 3
    assert len(recordings["2023-03-01"].items()) == 2
    assert len(recordings["2023-03-02"].items()) == 2
    assert len(recordings["2023-03-03"].items()) == 2
    assert recordings["2023-03-01"][1]["start_time"] == datetime.datetime(
        2023, 3, 1, 12, 0, tzinfo=datetime.timezone.utc
    )
    assert recordings["2023-03-01"][1]["end_time"] == datetime.datetime(
        2023, 3, 1, 12, 3, tzinfo=datetime.timezone.utc
    )


def test_get_recordings_date(get_db_session_recordings: Callable[[], Session]) -> None:
    """Test get_recording."""
    recordings = get_recordings(get_db_session_recordings, "test1", date="2023-03-03")
    assert len(recordings.items()) == 1
    assert recordings["2023-03-03"][6]["start_time"] == datetime.datetime(
        2023, 3, 3, 12, 10, tzinfo=datetime.timezone.utc
    )
    assert recordings["2023-03-03"][6]["end_time"] == datetime.datetime(
        2023, 3, 3, 12, 12, tzinfo=datetime.timezone.utc
    )


def test_get_recordings_latest(
    get_db_session_recordings: Callable[[], Session]
) -> None:
    """Test get_recording."""
    recordings = get_recordings(get_db_session_recordings, "test1", latest=True)
    assert len(recordings.items()) == 1
    assert len(recordings["2023-03-03"].items()) == 1
    assert recordings["2023-03-03"][6]["start_time"] == datetime.datetime(
        2023, 3, 3, 12, 10, tzinfo=datetime.timezone.utc
    )
    assert recordings["2023-03-03"][6]["end_time"] == datetime.datetime(
        2023, 3, 3, 12, 12, tzinfo=datetime.timezone.utc
    )


def test_get_recordings_latest_daily(
    get_db_session_recordings: Callable[[], Session]
) -> None:
    """Test get_recording."""
    recordings = get_recordings(
        get_db_session_recordings, "test1", latest=True, daily=True
    )
    assert len(recordings.items()) == 3
    assert len(recordings["2023-03-01"].items()) == 1
    assert len(recordings["2023-03-02"].items()) == 1
    assert len(recordings["2023-03-03"].items()) == 1
    assert recordings["2023-03-03"][6]["start_time"] == datetime.datetime(
        2023, 3, 3, 12, 10, tzinfo=datetime.timezone.utc
    )
    assert recordings["2023-03-03"][6]["end_time"] == datetime.datetime(
        2023, 3, 3, 12, 12, tzinfo=datetime.timezone.utc
    )


def test_get_recordings_date_latest(
    get_db_session_recordings: Callable[[], Session]
) -> None:
    """Test get_recording."""
    recordings = get_recordings(
        get_db_session_recordings, "test1", date="2023-03-01", latest=True
    )
    assert len(recordings.items()) == 1
    assert len(recordings["2023-03-01"].items()) == 1
    assert recordings["2023-03-01"][2]["start_time"] == datetime.datetime(
        2023, 3, 1, 12, 10, tzinfo=datetime.timezone.utc
    )
    assert recordings["2023-03-01"][2]["end_time"] == datetime.datetime(
        2023, 3, 1, 12, 12, tzinfo=datetime.timezone.utc
    )


def test_delete_recordings_single(get_db_session_recordings: Callable[[], Session]):
    """Test deleting a single recording."""
    recordings = delete_recordings(get_db_session_recordings, "test1", recording_id=1)
    assert len(recordings) == 1
    assert recordings[0].id == 1
    assert recordings[0].camera_identifier == "test1"


def test_delete_recordings_all(get_db_session_recordings: Callable[[], Session]):
    """Test deleting all recordings for a camera."""
    recordings = delete_recordings(get_db_session_recordings, "test1")
    assert len(recordings) == 6
    assert recordings[0].id == 1
    assert recordings[0].camera_identifier == "test1"


def test_delete_recordings_date(get_db_session_recordings: Callable[[], Session]):
    """Test deleting all recordings for a specific date for camera."""
    recordings = delete_recordings(
        get_db_session_recordings, "test1", date="2023-03-02"
    )
    assert len(recordings) == 2
    assert recordings[0].id == 3
    assert recordings[0].camera_identifier == "test1"


def test_delete_recordings_missing(get_db_session_recordings: Callable[[], Session]):
    """Test deleting a missing recording."""
    recordings = delete_recordings(
        get_db_session_recordings, "test_missing", recording_id=1
    )
    assert len(recordings) == 0


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
        recorder_base = RecorderBase(vis, MagicMock(), MockCamera())
        result = recorder_base.delete_recording()
        assert result is False

        mock_delete_recording.return_value = [
            MagicMock(spec=Recordings),
            MagicMock(spec=Recordings),
        ]
        result = recorder_base.delete_recording()
        assert result is True
