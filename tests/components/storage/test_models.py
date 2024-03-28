"""Tests for the database models."""

import datetime

from viseron.components.storage.models import Recordings

from tests.common import BaseTestWithRecordings


class TestRecordings(BaseTestWithRecordings):
    """Test the Recordings model."""

    def test_get_files(self):
        """Test get_files."""
        with self._get_db_session() as session:
            recording = session.query(Recordings).filter_by(id=3).one()
        rows = recording.get_fragments(5, self._get_db_session)
        assert len(rows) == 4
        assert rows[0].created_at == self._now + datetime.timedelta(seconds=20)
        assert rows[3].created_at == self._now + datetime.timedelta(seconds=35)
