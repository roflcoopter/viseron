"""Test the query functions."""

import datetime
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import update
from sqlalchemy.exc import NoResultFound

from viseron.components.storage.check_tier import (
    Worker,
    copy_file_for_tier_worker,
    delete_file,
    get_files_to_move,
    get_recordings_to_move,
    load_recordings,
    load_tier,
    move_file_for_tier_worker,
)
from viseron.components.storage.models import Recordings
from viseron.components.storage.storage_subprocess import DataItem

from tests.common import BaseTestWithRecordings


class FakeScalarResult:
    """Fake SQLAlchemy scalar result."""

    def scalar_one(self) -> None:
        """Raise no result found."""
        raise NoResultFound


class FakeSession:
    """Fake SQLAlchemy session."""

    def __init__(self) -> None:
        self.executed = False
        self.committed = False

    def __enter__(self):
        """Return context manager session."""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Exit context manager."""

    def execute(self, _stmt):
        """Record statement execution."""
        self.executed = True
        return FakeScalarResult()

    def commit(self) -> None:
        """Record commit."""
        self.committed = True


def test_check_tier_throttles_recent_non_forced_check() -> None:
    """Recent tier checks should be throttled by default."""
    item = DataItem(
        cmd="check_tier",
        camera_identifier="test",
        tier_id=0,
        category="recorder",
        subcategories=["segments"],
        throttle_period=datetime.timedelta(minutes=1),
        max_bytes=0,
        min_age=datetime.timedelta(seconds=0),
        max_age=datetime.timedelta(seconds=0),
        min_bytes=0,
        drain=False,
    )
    worker = Worker.__new__(Worker)
    worker._last_call = {item.throttle_key: datetime.datetime.now().timestamp()}
    worker._check_locks = {}
    worker._checks_in_progress = {}
    worker._check_tier = MagicMock()

    worker.check_tier(item)

    worker._check_tier.assert_not_called()
    assert item.data is None


def test_check_tier_force_bypasses_recent_throttle() -> None:
    """Forced tier checks should bypass the worker throttle."""
    item = DataItem(
        cmd="check_tier",
        camera_identifier="test",
        tier_id=0,
        category="recorder",
        subcategories=["segments"],
        throttle_period=datetime.timedelta(minutes=1),
        max_bytes=0,
        min_age=datetime.timedelta(seconds=0),
        max_age=datetime.timedelta(seconds=0),
        min_bytes=0,
        drain=False,
        force=True,
    )
    worker = Worker.__new__(Worker)
    worker._last_call = {item.throttle_key: datetime.datetime.now().timestamp()}
    worker._check_locks = {}
    worker._checks_in_progress = {}
    worker._check_tier = MagicMock()

    worker.check_tier(item)

    worker._check_tier.assert_called_once_with(item)


class TestFileOperations:
    """Test destructive file operations."""

    def test_move_file_destination_error_keeps_source_state(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Destination failures must not delete source file or DB row."""
        src = tmp_path / "src.m4s"
        dst = tmp_path / "dst.m4s"
        src.write_bytes(b"segment")
        session = FakeSession()

        def raise_oserror(_src: str, _dst: str) -> int:
            raise OSError("destination unavailable")

        monkeypatch.setattr(
            "viseron.components.storage.check_tier.move_file_atomic",
            raise_oserror,
        )

        with pytest.raises(OSError, match="destination unavailable"):
            move_file_for_tier_worker(lambda: session, str(src), str(dst), MagicMock())

        assert src.exists()
        assert session.executed is False
        assert session.committed is False

    def test_move_file_missing_source_deletes_stale_db_row(self, tmp_path) -> None:
        """Missing source means stale DB state, not a retryable move."""
        src = tmp_path / "missing.m4s"
        dst = tmp_path / "dst.m4s"
        session = FakeSession()

        result = move_file_for_tier_worker(
            lambda: session, str(src), str(dst), MagicMock()
        )

        assert result.moved is False
        assert result.published is False
        assert result.source_missing is True
        assert result.source_removed is False
        assert result.source_remove_error is None
        assert result.size is None
        assert session.executed is True
        assert session.committed is True

    def test_move_file_source_remove_error_reports_published(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed source cleanup must still report the destination as published."""
        src = tmp_path / "src.m4s"
        dst = tmp_path / "dst.m4s"
        src.write_bytes(b"segment")
        session = FakeSession()
        real_remove = os.remove

        def remove_with_source_error(path: str) -> None:
            if path == str(src):
                raise OSError("unlink failed")
            real_remove(path)

        monkeypatch.setattr(
            "viseron.components.storage.util.os.remove",
            remove_with_source_error,
        )

        result = move_file_for_tier_worker(
            lambda: session, str(src), str(dst), MagicMock()
        )

        assert result.moved is True
        assert result.published is True
        assert result.source_missing is False
        assert result.source_removed is False
        assert result.source_remove_error == "unlink failed"
        assert result.size == len(b"segment")
        assert src.exists()
        assert dst.read_bytes() == b"segment"
        assert session.executed is False
        assert session.committed is False

    def test_move_file_replace_error_after_publish_reports_published(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An ACK-lost replace should commit if the destination verifies."""
        src = tmp_path / "src.m4s"
        dst = tmp_path / "dst.m4s"
        src.write_bytes(b"segment")
        session = FakeSession()
        real_replace = os.replace

        def replace_then_error(src_path: str, dst_path: str) -> None:
            real_replace(src_path, dst_path)
            raise OSError("replace ack lost")

        monkeypatch.setattr(
            "viseron.components.storage.util.os.replace",
            replace_then_error,
        )

        result = move_file_for_tier_worker(
            lambda: session, str(src), str(dst), MagicMock()
        )

        assert result.moved is True
        assert result.published is True
        assert result.source_missing is False
        assert result.source_removed is True
        assert result.source_remove_error is None
        assert result.size == len(b"segment")
        assert not src.exists()
        assert dst.read_bytes() == b"segment"
        assert session.executed is False
        assert session.committed is False

    def test_delete_file_transient_error_keeps_db_row(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed remove should not delete the DB row."""
        src = tmp_path / "src.m4s"
        src.write_bytes(b"segment")
        session = FakeSession()

        def raise_oserror(_path: str) -> None:
            raise OSError("remove failed")

        monkeypatch.setattr(
            "viseron.components.storage.check_tier.os.remove", raise_oserror
        )

        with pytest.raises(OSError, match="remove failed"):
            delete_file(lambda: session, str(src), MagicMock())

        assert session.executed is False
        assert session.committed is False

    def test_move_file_unavailable_parent_keeps_db_row(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unavailable source/destination parents should not delete DB rows."""
        src = tmp_path / "src.m4s"
        dst = tmp_path / "dst.m4s"
        src.write_bytes(b"segment")
        session = FakeSession()

        def raise_oserror(_path: str) -> None:
            raise OSError("parent unavailable")

        monkeypatch.setattr(
            "viseron.components.storage.check_tier.raise_if_path_unavailable",
            raise_oserror,
        )

        with pytest.raises(OSError, match="parent unavailable"):
            move_file_for_tier_worker(lambda: session, str(src), str(dst), MagicMock())

        assert session.executed is False
        assert session.committed is False

    def test_copy_file_copies_without_removing_source(self, tmp_path) -> None:
        """Copying sidecars should publish dst and preserve src."""
        src = tmp_path / "src" / "init.mp4"
        dst = tmp_path / "dst" / "init.mp4"
        src.parent.mkdir()
        dst.parent.mkdir()
        src.write_bytes(b"init")

        result = copy_file_for_tier_worker(str(src), str(dst), MagicMock())

        assert result.copied is True
        assert result.published is True
        assert result.source_missing is False
        assert result.size == len(b"init")
        assert src.read_bytes() == b"init"
        assert dst.read_bytes() == b"init"

    def test_copy_file_missing_source_reports_existing_destination(
        self, tmp_path
    ) -> None:
        """A missing source is OK if the destination sidecar already exists."""
        src = tmp_path / "src" / "init.mp4"
        dst = tmp_path / "dst" / "init.mp4"
        src.parent.mkdir()
        dst.parent.mkdir()
        dst.write_bytes(b"init")

        result = copy_file_for_tier_worker(str(src), str(dst), MagicMock())

        assert result.copied is False
        assert result.published is True
        assert result.source_missing is True
        assert result.size == len(b"init")


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
            drain=True,
        )

        assert item.data is not None
        assert len(item.data) == len(expected)
        assert list(item.data["id"]) == list(expected["id"])
