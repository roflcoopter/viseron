"""Tests for the database models."""

import datetime
from typing import Any, Callable, Generator

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from viseron.components.storage.models import Files, FilesMeta, Recordings


class TestRecordings:
    """Test the Recordings model."""

    _get_session: Callable[[], Session]
    _now: datetime.datetime

    @pytest.fixture(autouse=True, scope="class")
    def setup_class_fixture(
        self, get_db_session_class: Callable[[], Session]
    ) -> Generator[None, Any, None]:
        """Insert data used by all tests."""
        TestRecordings._get_session = get_db_session_class
        TestRecordings._now = datetime.datetime.now()

        with get_db_session_class() as session:
            for i in range(15):
                timestamp = self._now + datetime.timedelta(seconds=5 * i)
                filename = f"{int(timestamp.timestamp())}.m4s"
                session.execute(
                    insert(Files).values(
                        tier_id=1,
                        camera_identifier="test",
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
            session.execute(
                insert(Recordings).values(
                    camera_identifier="test",
                    start_time=self._now + datetime.timedelta(seconds=17),
                    end_time=self._now + datetime.timedelta(seconds=27),
                    created_at=self._now + datetime.timedelta(seconds=17),
                    thumbnail_path="/test/test1.jpg",
                )
            )
            session.commit()
            yield

    def test_get_files(self):
        """Test get_files."""
        with self._get_session() as session:
            recording = session.query(Recordings).filter_by(id=1).one()
        rows = recording.get_files(5, self._get_session)
        assert len(rows) == 4
        assert rows[0][0].created_at == self._now + datetime.timedelta(seconds=10)
        assert rows[3][0].created_at == self._now + datetime.timedelta(seconds=25)
