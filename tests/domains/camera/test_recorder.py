"""Tests for recorder."""
from __future__ import annotations

import datetime
from typing import Callable

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from viseron.components.storage.models import Files, FilesMeta, Recordings
from viseron.domains.camera.recorder import Recording, get_recordings


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
        2023, 3, 1, 12, 0
    )
    assert recordings["2023-03-01"][1]["end_time"] == datetime.datetime(
        2023, 3, 1, 12, 3
    )


def test_get_recordings_date(get_db_session_recordings: Callable[[], Session]) -> None:
    """Test get_recording."""
    recordings = get_recordings(get_db_session_recordings, "test1", date="2023-03-03")
    assert len(recordings.items()) == 1
    assert recordings["2023-03-03"][6]["start_time"] == datetime.datetime(
        2023, 3, 3, 12, 10
    )
    assert recordings["2023-03-03"][6]["end_time"] == datetime.datetime(
        2023, 3, 3, 12, 12
    )


def test_get_recordings_latest(
    get_db_session_recordings: Callable[[], Session]
) -> None:
    """Test get_recording."""
    recordings = get_recordings(get_db_session_recordings, "test1", latest=True)
    assert len(recordings.items()) == 1
    assert len(recordings["2023-03-03"].items()) == 1
    assert recordings["2023-03-03"][6]["start_time"] == datetime.datetime(
        2023, 3, 3, 12, 10
    )
    assert recordings["2023-03-03"][6]["end_time"] == datetime.datetime(
        2023, 3, 3, 12, 12
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
        2023, 3, 3, 12, 10
    )
    assert recordings["2023-03-03"][6]["end_time"] == datetime.datetime(
        2023, 3, 3, 12, 12
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
        2023, 3, 1, 12, 10
    )
    assert recordings["2023-03-01"][2]["end_time"] == datetime.datetime(
        2023, 3, 1, 12, 12
    )


class TestRecording:
    """Test the Recording dataclass."""

    def test_get_fragments(self, get_db_session_recordings: Callable[[], Session]):
        """Test get_fragments."""
        with get_db_session_recordings() as session:
            start = datetime.datetime(2023, 3, 1, 11, 59, 50)
            for i in range(15):
                timestamp = start + datetime.timedelta(seconds=5 * i)
                filename = f"{int(timestamp.timestamp())}.m4s"
                session.execute(
                    insert(Files).values(
                        tier_id=1,
                        camera_identifier="test1",
                        category="recorder",
                        path=f"/test/{filename}",
                        directory="test",
                        filename=filename,
                        size=10,
                        created_at=timestamp,
                    )
                )
                session.execute(
                    insert(FilesMeta).values(
                        path=f"/test/{filename}",
                        meta={"m3u8": {"EXTINF": 5}},
                        created_at=timestamp,
                    )
                )
            # Simulate a file that has been moved a up tier but have not been removed
            # from the previous tier yet
            created_at = timestamp + datetime.timedelta(seconds=5)
            timestamp = timestamp - datetime.timedelta(seconds=25)
            filename = f"{int(timestamp.timestamp())}.m4s"
            session.execute(
                insert(Files).values(
                    tier_id=2,
                    camera_identifier="test1",
                    category="recorder",
                    path=f"/test2/{filename}",
                    directory="test2",
                    filename=filename,
                    size=10,
                    created_at=created_at,
                )
            )
            session.execute(
                insert(FilesMeta).values(
                    path=f"/test2/{filename}",
                    meta={"m3u8": {"EXTINF": 5}},
                    created_at=created_at,
                )
            )
            session.commit()

        recording = Recording(
            id=1,
            start_time=datetime.datetime(2023, 3, 1, 12, 0, 0),
            start_timestamp=datetime.datetime(2023, 3, 1, 12, 0, 0).timestamp(),
            end_time=datetime.datetime(2023, 3, 1, 12, 0, 50),
            end_timestamp=datetime.datetime(2023, 3, 1, 12, 0, 50).timestamp(),
            date="2023-03-01",
            path="test",
            filename="test.mp4",
            thumbnail=None,
            thumbnail_path=None,
            objects=[],
        )
        files = recording.get_fragments(5, get_db_session_recordings)
        assert len(files) == 12
        assert files[0].created_at == datetime.datetime(2023, 3, 1, 11, 59, 55)
        assert files[-1].created_at == datetime.datetime(2023, 3, 1, 12, 0, 50)
        assert files[8].tier_id == 2
