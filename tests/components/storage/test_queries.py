"""Test the query functions."""
import datetime

from sqlalchemy import insert

from viseron.components.storage.models import Files
from viseron.components.storage.queries import (
    get_recording_fragments,
    get_time_period_fragments,
)

from tests.common import BaseTestWithRecordings


class TestQueries(BaseTestWithRecordings):
    """Test the moving of files query functions."""

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
                    tier_path="/tier2/",
                    camera_identifier="test",
                    category="recorder",
                    subcategory="segments",
                    path=f"/tier2/{filename}",
                    directory="tier2",
                    filename=filename,
                    size=10,
                    orig_ctime=timestamp,
                    duration=5,
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

    def test_get_time_period_fragments(self):
        """Test get_recording_fragments."""
        with self._get_db_session() as session:
            # Simulate a file that has been moved a up tier but have not been removed
            # from the previous tier yet
            created_at = self._now + datetime.timedelta(seconds=55)
            timestamp = self._now + datetime.timedelta(seconds=25)
            filename = f"{int(timestamp.timestamp())}.m4s"
            session.execute(
                insert(Files).values(
                    tier_id=1,
                    tier_path="/tier2/",
                    camera_identifier="test",
                    category="recorder",
                    subcategory="segments",
                    path=f"/tier2/{filename}",
                    directory="tier2",
                    filename=filename,
                    size=10,
                    orig_ctime=timestamp,
                    duration=5,
                    created_at=created_at,
                )
            )

            # Simulate a file that has broken metadata
            created_at = self._now + datetime.timedelta(seconds=500)
            timestamp = self._now + datetime.timedelta(seconds=500)
            filename = f"{int(timestamp.timestamp())}.m4s"
            session.execute(
                insert(Files).values(
                    tier_id=0,
                    tier_path="/tier1/",
                    camera_identifier="test",
                    category="recorder",
                    subcategory="segments",
                    path=f"/tier1/{filename}",
                    directory="tier1",
                    filename=filename,
                    size=10,
                    orig_ctime=timestamp,
                    duration=None,
                    created_at=created_at,
                )
            )
            session.commit()

        files = get_time_period_fragments(
            ["test"],
            0,
            None,
            self._get_db_session,
            self._now + datetime.timedelta(days=365),
        )
        assert len(files) == 15
        assert files[4].tier_id == 0
        assert files[5].tier_id == 1
