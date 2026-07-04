"""Test the TierHandler class."""

from dataclasses import dataclass
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
from sqlalchemy import select
from watchdog.events import FileCreatedEvent, FileMovedEvent

from viseron import Viseron
from viseron.components.storage import Storage
from viseron.components.storage.const import (
    COMPONENT as STORAGE_COMPONENT,
    CONFIG_RECORDER,
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
)
from viseron.components.storage.models import Files, FilesMeta, Recordings
from viseron.components.storage.storage_subprocess import (
    DataItemCopyFile,
    DataItemMoveFile,
)
from viseron.components.storage.tier_handler import (
    EventClipTierHandler,
    SegmentsTierHandler,
    TierHandler,
    ThumbnailTierHandler,
    find_next_tier_segments,
    handle_file,
    move_file as tier_handler_move_file,
)
from viseron.domains.camera.const import CONFIG_CONTINUOUS_RECORDING, CONFIG_LOOKBACK
from viseron.helpers import utcnow

from tests.common import BaseTestWithRecordings
from tests.conftest import MockViseron


class MoveCallbackScalarResult:
    """Fake scalar result for move callback tests."""

    def __init__(self, row) -> None:
        self._row = row

    def scalar_one(self):
        """Return fake row."""
        return self._row


class MoveCallbackRowcountResult:
    """Fake rowcount result for move callback tests."""

    rowcount = 1


class MoveCallbackSession:
    """Fake session for move callback tests."""

    def __init__(self) -> None:
        self.execute_count = 0
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        """Return context manager session."""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Exit context manager."""

    def execute(self, _stmt):
        """Return metadata row first, then successful update result."""
        self.execute_count += 1
        if self.execute_count == 1:
            return MoveCallbackScalarResult(
                MagicMock(orig_ctime=utcnow(), duration=1.0)
            )
        return MoveCallbackRowcountResult()

    def commit(self) -> None:
        """Record commit."""
        self.committed = True

    def rollback(self) -> None:
        """Record rollback."""
        self.rolled_back = True


def test_on_any_event_ignores_storage_temp_file() -> None:
    """Internal temporary files should not be queued for DB insertion."""
    tier_handler = TierHandler.__new__(TierHandler)
    tier_handler._storage = MagicMock(ignored_files=[])
    tier_handler._event_queue = MagicMock()

    tier_handler.on_any_event(FileCreatedEvent("/tmp/.viseron-tmp-file.m4s.1.abc"))

    tier_handler._event_queue.put.assert_not_called()


def test_on_any_event_queues_moved_file_from_storage_temp_file() -> None:
    """Atomic publishes should be treated as destination create events."""
    tier_handler = TierHandler.__new__(TierHandler)
    tier_handler._storage = MagicMock(ignored_files=[])
    tier_handler._event_queue = MagicMock()
    tier_handler._path = "/tmp"
    event = FileMovedEvent(
        "/tmp/.viseron-tmp-file.m4s.1.abc",
        "/tmp/file.m4s",
    )

    tier_handler.on_any_event(event)

    tier_handler._event_queue.put.assert_called_once_with(event)


def test_on_created_missing_file_does_not_pop_metadata(tmp_path) -> None:
    """A disappeared create event should not kill the handler or consume metadata."""
    path = str(tmp_path / "missing.m4s")
    tier_handler = TierHandler.__new__(TierHandler)
    tier_handler._logger = MagicMock()
    tier_handler._storage = MagicMock()
    tier_handler._storage.temporary_files_meta = {path: MagicMock()}

    tier_handler._on_created(FileCreatedEvent(path))

    assert path in tier_handler._storage.temporary_files_meta


def test_on_created_duplicate_path_is_ignored(
    tmp_path, get_db_session, vis: MockViseron
) -> None:
    """Duplicate create events for the same path should be database no-ops."""
    path = str(tmp_path / "duplicate.m4s")
    with open(path, "wb") as file:
        file.write(b"segment")

    tier_handler = TierHandler.__new__(TierHandler)
    tier_handler._logger = MagicMock()
    tier_handler._vis = vis
    tier_handler._storage = MagicMock()
    tier_handler._storage.get_session = get_db_session
    tier_handler._storage.temporary_files_meta = {
        path: FilesMeta(orig_ctime=utcnow(), duration=5.0)
    }
    tier_handler._camera = MagicMock(identifier="test")
    tier_handler._tier_id = 1
    tier_handler._tier = {"path": "/"}
    tier_handler._category = TIER_CATEGORY_RECORDER
    tier_handler._subcategory = TIER_SUBCATEGORY_SEGMENTS
    tier_handler.check_tier = MagicMock()

    tier_handler._on_created(FileCreatedEvent(path))
    tier_handler._storage.temporary_files_meta[path] = FilesMeta(
        orig_ctime=utcnow(), duration=5.0
    )
    tier_handler._on_created(FileCreatedEvent(path))

    with get_db_session() as session:
        files = session.execute(select(Files).where(Files.path == path)).all()

    assert len(files) == 1
    assert vis.dispatch_event.call_count == 1
    assert tier_handler.check_tier.call_count == 2


def test_move_file_callback_commits_published_move() -> None:
    """A published destination should commit even when source cleanup failed."""
    src = "/tier1/segments/camera/1.m4s"
    dst = "/tier2/segments/camera/1.m4s"
    session = MoveCallbackSession()
    vis = MagicMock()
    storage = MagicMock()
    storage.temporary_files_meta = {}

    tier_handler_move_file(
        vis,
        storage,
        lambda: session,
        "camera",
        0,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
        1,
        "/tier2",
        src,
        dst,
        MagicMock(),
    )

    copy_call = storage.tier_check_worker_send_command.call_args_list[0]
    assert isinstance(copy_call.args[0], DataItemCopyFile)
    assert copy_call.args[0].src == "/tier1/segments/camera/init.mp4"
    assert copy_call.args[0].dst == "/tier2/segments/camera/init.mp4"

    copy_callback = copy_call.kwargs["callback"]
    copy_callback(
        DataItemCopyFile(
            cmd="copy_file",
            src="/tier1/segments/camera/init.mp4",
            dst="/tier2/segments/camera/init.mp4",
            copied=True,
            published=True,
            size=4,
        )
    )

    move_call = storage.tier_check_worker_send_command.call_args_list[1]
    assert isinstance(move_call.args[0], DataItemMoveFile)
    callback = move_call.kwargs["callback"]
    callback(
        DataItemMoveFile(
            cmd="move_file",
            src=src,
            dst=dst,
            moved=True,
            published=True,
            source_removed=False,
            source_remove_error="unlink failed",
            size=7,
        )
    )

    assert session.committed is True
    assert session.rolled_back is False
    assert session.execute_count == 2
    assert dst not in storage.temporary_files_meta
    vis.dispatch_event.assert_called_once()


def test_move_file_skips_segment_move_when_init_sidecar_missing() -> None:
    """A segment should not be moved to a tier without init.mp4."""
    src = "/tier1/segments/camera/1.m4s"
    dst = "/tier2/segments/camera/1.m4s"
    session = MoveCallbackSession()
    storage = MagicMock()
    storage.temporary_files_meta = {}

    tier_handler_move_file(
        MagicMock(),
        storage,
        lambda: session,
        "camera",
        0,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
        1,
        "/tier2",
        src,
        dst,
        MagicMock(),
    )

    copy_call = storage.tier_check_worker_send_command.call_args_list[0]
    copy_callback = copy_call.kwargs["callback"]
    copy_callback(
        DataItemCopyFile(
            cmd="copy_file",
            src="/tier1/segments/camera/init.mp4",
            dst="/tier2/segments/camera/init.mp4",
            source_missing=True,
            published=False,
        )
    )

    assert storage.tier_check_worker_send_command.call_count == 1
    assert dst not in storage.temporary_files_meta


@patch("viseron.components.storage.tier_handler.delete_file")
def test_handle_file_delete(mock_delete_file: Mock, vis: MockViseron) -> None:
    """Test handle_file."""
    file = "/tmp/tier1/file1"
    tier_1 = {
        "path": "/tmp/tier1",
    }
    tier_2 = None
    session = MagicMock()
    logger = MagicMock()
    storage = MagicMock()
    handle_file(
        vis,
        session,
        storage,
        "test",
        0,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
        tier_1,
        tier_2,
        file,
        "/tmp/tier1/",
        logger,
    )
    mock_delete_file.assert_called_once_with(storage, file)


@patch("viseron.components.storage.tier_handler.move_file")
def test_handle_file_move(mock_move_file: Mock, vis: MockViseron) -> None:
    """Test handle_file."""
    tier_1_file = "/tmp/tier1/file1"
    tier_2_file = "/tmp/tier2/file1"
    tier_1 = {
        "path": "/tmp/tier1/",
    }
    tier_2 = {
        "path": "/tmp/tier2/",
    }
    storage = MagicMock()
    session = MagicMock()
    logger = MagicMock()
    handle_file(
        vis,
        session,
        storage,
        "test",
        0,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
        tier_1,
        tier_2,
        tier_1_file,
        "/tmp/tier1/",
        logger,
    )
    mock_move_file.assert_called_once_with(
        vis,
        storage,
        session,
        "test",
        0,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
        1,
        "/tmp/tier2/",
        tier_1_file,
        tier_2_file,
        logger,
    )


@dataclass
class MockRecordingsQueryResult:
    """Mock query result."""

    recording_id: int | None
    file_id: int
    path: str
    tier_path: str


@dataclass
class MockFilesQueryResult:
    """Mock query result."""

    id: int
    path: str
    tier_path: str


def _get_tier_config(events: bool, continuous: bool):
    """Get tier config for test."""
    max_age_events = None
    max_age_continuous = None
    if events:
        max_age_events = 1
    if continuous:
        max_age_continuous = 1
    return {
        "path": "/",
        "events": {
            "max_age": {"days": max_age_events, "hours": None, "minutes": None},
            "min_age": {"hours": None, "days": None, "minutes": None},
            "min_size": {"gb": None, "mb": None},
            "max_size": {"gb": None, "mb": None},
        },
        "move_on_shutdown": False,
        "poll": False,
        "continuous": {
            "max_age": {"minutes": max_age_continuous, "hours": None, "days": None},
            "min_age": {"minutes": None, "hours": None, "days": None},
            "min_size": {"gb": None, "mb": None},
            "max_size": {"gb": None, "mb": None},
        },
        "check_interval": {
            "days": 0,
            "hours": 0,
            "minutes": 1,
            "seconds": 0,
        },
    }


class TestSegmentsTierHandler(BaseTestWithRecordings):
    """Test the SegmentsTierHandler class."""

    @pytest.mark.parametrize(
        ("tier, data, recordings_amount, first_recording_id"),
        [
            (
                _get_tier_config(events=True, continuous=False),
                np.array(
                    [
                        (
                            1,
                            1,
                            "/tmp/test1.mp4",
                            "/tmp/",
                        ),
                        (
                            1,
                            2,
                            "/tmp/test2.mp4",
                            "/tmp/",
                        ),
                    ],
                    dtype=(
                        [
                            ("recording_id", np.int64),
                            ("id", np.int64),
                            ("path", "U512"),
                            ("tier_path", "U512"),
                        ]
                    ),
                ),
                2,
                3,
            ),
            (
                _get_tier_config(events=True, continuous=True),
                np.array(
                    [
                        (
                            1,
                            1,
                            "/tmp/test1.mp4",
                            "/tmp/",
                        ),
                        (
                            1,
                            2,
                            "/tmp/test2.mp4",
                            "/tmp/",
                        ),
                    ],
                    dtype=(
                        [
                            ("recording_id", np.int64),
                            ("id", np.int64),
                            ("path", "U512"),
                            ("tier_path", "U512"),
                        ]
                    ),
                ),
                2,
                3,
            ),
            (
                _get_tier_config(events=False, continuous=True),
                np.array(
                    [
                        (
                            -1,
                            1,
                            "/tmp/test1.mp4",
                            "/tmp/",
                        ),
                        (
                            -1,
                            2,
                            "/tmp/test2.mp4",
                            "/tmp/",
                        ),
                    ],
                    dtype=(
                        [
                            ("recording_id", np.int64),
                            ("id", np.int64),
                            ("path", "U512"),
                            ("tier_path", "U512"),
                        ]
                    ),
                ),
                3,
                1,
            ),
        ],
    )
    def test__check_tier(
        self,
        vis,
        tier,
        data,
        recordings_amount,
        first_recording_id,
    ):
        """Test _check_tier."""

        mock_camera = Mock()
        mock_camera.identifier = "test"
        mock_camera.config = {
            CONFIG_RECORDER: {CONFIG_LOOKBACK: 5, CONFIG_CONTINUOUS_RECORDING: True}
        }

        tier_handler = SegmentsTierHandler(
            vis,
            mock_camera,
            0,
            "recorder",
            "segments",
            tier,
            None,
        )

        with patch("viseron.components.storage.tier_handler.handle_file"):
            tier_handler._check_tier(self._get_db_session, data)

        with self._get_db_session() as session:
            stmt = select(Recordings).where(
                Recordings.camera_identifier == mock_camera.identifier
            )
            recordings = session.execute(stmt).scalars().fetchall()
            assert len(recordings) == recordings_amount
            assert recordings[0].id == first_recording_id

    @pytest.mark.parametrize(
        "tiers_config, recording_id, force_delete, next_tier_index, "
        "move_thumbnail_called, move_event_clip_called",
        [
            (  # Test that check_tier deletes the file if next tier is None
                [_get_tier_config(events=True, continuous=True)],
                1,
                True,
                None,
                True,
                True,
            ),
            # Test that check_tier deletes the file if its not part of a recording and
            # next tier does not store continuous
            (
                [
                    _get_tier_config(events=True, continuous=True),
                    _get_tier_config(events=True, continuous=False),
                ],
                None,
                True,
                None,
                False,
                False,
            ),
            # Test that check_tier moves the file if its part of a recording and
            # the next tier stores events
            (
                [
                    _get_tier_config(events=True, continuous=True),
                    _get_tier_config(events=True, continuous=False),
                ],
                1,
                False,
                1,
                True,
                True,
            ),
            # Test that check_tier moves the file to the correct tier when the next tier
            # does not store events but the next next tier does
            (
                [
                    _get_tier_config(events=True, continuous=True),
                    _get_tier_config(events=False, continuous=False),
                    _get_tier_config(events=True, continuous=False),
                    _get_tier_config(events=False, continuous=True),
                ],
                1,
                False,
                2,
                True,
                True,
            ),
        ],
    )
    def test__check_tier_next_tier(
        self,
        vis: Viseron,
        tiers_config,
        recording_id: int,
        force_delete: bool,
        next_tier_index: int | None,
        move_thumbnail_called: bool,
        move_event_clip_called: bool,
    ):
        """Test that check_tier finds the correct tier."""
        mock_camera = Mock()
        mock_camera.identifier = "test"
        mock_camera.config = {
            CONFIG_RECORDER: {CONFIG_LOOKBACK: 5, CONFIG_CONTINUOUS_RECORDING: True}
        }

        tier_handlers = []
        for i, tier_config in enumerate(tiers_config):
            tier_handler = SegmentsTierHandler(
                vis,
                mock_camera,
                i,
                TIER_CATEGORY_RECORDER,
                TIER_SUBCATEGORY_SEGMENTS,
                tier_config,
                None,
            )
            tier_handlers.append(tier_handler)
        recordings_tier_handler = MagicMock(spec=EventClipTierHandler)
        thumbnail_tier_handler = MagicMock(spec=ThumbnailTierHandler)
        vis.data[STORAGE_COMPONENT].camera_tier_handlers = {
            "test": {
                "recorder": [
                    {
                        "segments": tier_handler,
                        "thumbnails": thumbnail_tier_handler,
                        "event_clips": recordings_tier_handler,
                    }
                    for tier_handler in tier_handlers
                ]
            }
        }

        with patch(
            "viseron.components.storage.tier_handler.handle_file"
        ) as mock_handle_file:
            data = np.array(
                [
                    (
                        recording_id if recording_id is not None else -1,
                        1,
                        "/tmp/test1.mp4",
                        "/tmp/",
                    )
                ],
                dtype=[
                    ("recording_id", np.int64),
                    ("id", np.int64),
                    ("path", "U512"),
                    ("tier_path", "U512"),
                ],
            )
            tier_handlers[0]._check_tier(self._get_db_session, data)
            mock_handle_file.assert_called_once_with(
                tier_handlers[0]._vis,
                self._get_db_session,
                tier_handlers[0]._storage,
                tier_handlers[0]._camera.identifier,
                tier_handlers[0].tier_id,
                TIER_CATEGORY_RECORDER,
                TIER_SUBCATEGORY_SEGMENTS,
                tier_handlers[0].tier,
                tier_handlers[next_tier_index].tier if next_tier_index else None,
                "/tmp/test1.mp4",
                "/tmp/",
                tier_handlers[0]._logger,
                force_delete=force_delete,
                next_tier_id=tier_handlers[next_tier_index].tier_id
                if next_tier_index
                else None,
            )
            if move_thumbnail_called:
                thumbnail_tier_handler.move_thumbnail.assert_called_once_with(
                    1, tier_handlers[next_tier_index].tier if next_tier_index else None
                )
            if move_event_clip_called:
                recordings_tier_handler.move_event_clip.assert_called_once_with(
                    1, tier_handlers[next_tier_index].tier if next_tier_index else None
                )


def test_find_next_tier_segments(vis: Viseron):
    """Test find_next_tier_segments."""
    mock_storage = Mock(spec=Storage)
    mock_camera = Mock()
    mock_camera.identifier = "test_camera"
    mock_camera.config = {
        CONFIG_RECORDER: {CONFIG_LOOKBACK: 5, CONFIG_CONTINUOUS_RECORDING: True}
    }

    tier_handler_0 = SegmentsTierHandler(
        vis,
        mock_camera,
        0,
        "recorder",
        "segments",
        _get_tier_config(events=True, continuous=True),
        None,
    )
    tier_handler_1 = SegmentsTierHandler(
        vis,
        mock_camera,
        1,
        "recorder",
        "segments",
        _get_tier_config(events=False, continuous=False),
        None,
    )
    tier_handler_2 = SegmentsTierHandler(
        vis,
        mock_camera,
        2,
        "recorder",
        "segments",
        _get_tier_config(events=True, continuous=False),
        None,
    )

    tier_handler_3 = SegmentsTierHandler(
        vis,
        mock_camera,
        3,
        "recorder",
        "segments",
        _get_tier_config(events=False, continuous=True),
        None,
    )

    mock_camera.identifier = "test_camera"
    mock_storage.camera_tier_handlers = {
        "test_camera": {
            "recorder": [
                {"segments": tier_handler_0},
                {"segments": tier_handler_1},
                {"segments": tier_handler_2},
                {"segments": tier_handler_3},
            ]
        }
    }

    result = find_next_tier_segments(mock_storage, 0, mock_camera, "events")
    assert result == tier_handler_2

    result = find_next_tier_segments(mock_storage, 0, mock_camera, "continuous")
    assert result == tier_handler_3

    result = find_next_tier_segments(mock_storage, 2, mock_camera, "events")
    assert result is None
