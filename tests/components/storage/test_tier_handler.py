"""Test the TierHandler class."""

from __future__ import annotations

import logging
import os
import shutil
import threading
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
from numpy._typing._array_like import NDArray
from sqlalchemy import select
from watchdog.events import FileCreatedEvent, FileDeletedEvent

from viseron import Viseron
from viseron.components.storage import Storage
from viseron.components.storage.const import (
    COMPONENT as STORAGE_COMPONENT,
    CONFIG_DRAIN,
    CONFIG_PATH,
    CONFIG_RECORDER,
    LATEST_SNAPSHOT_FILENAME,
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
)
from viseron.components.storage.models import (
    Files,
    FilesMeta,
    Recordings,
)
from viseron.components.storage.storage_subprocess import DataItemMoveFile
from viseron.components.storage.tier_handler import (
    EventClipTierHandler,
    SegmentsTierHandler,
    SnapshotTierHandler,
    ThumbnailTierHandler,
    TierHandler,
    find_next_tier_segments,
    handle_file,
    move_file,
)
from viseron.components.storage.util import EventFileCreated
from viseron.domains.camera.const import (
    CONFIG_CONTINUOUS_RECORDING,
    CONFIG_LOOKBACK,
    CONFIG_SCHEDULE,
    CONFIG_SCHEDULE_CONTINUOUS,
    CONFIG_SCHEDULE_TIMEZONE,
)
from viseron.helpers import utcnow

from tests.common import BaseTestWithRecordings
from tests.conftest import MockViseron

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

_TierHandlerT = TypeVar("_TierHandlerT", bound=TierHandler)


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
        tier_1_file,
        tier_2_file,
        "/tmp/tier2/",
        logger,
    )


def test_snapshot_tier_handler_ignores_the_latest_snapshot() -> None:
    """Test that latest_snapshot.jpg is exempt from the database and tier moves."""
    tier_handler = SnapshotTierHandler.__new__(SnapshotTierHandler)
    tier_handler._path = "/snapshots/face_recognition/test_camera"
    tier_handler._storage = MagicMock(spec=Storage)
    tier_handler.add_file_handler = MagicMock()  # type: ignore[method-assign]

    with patch.object(TierHandler, "initialize"):
        tier_handler.initialize()

    tier_handler._storage.ignore_file.assert_called_once_with(LATEST_SNAPSHOT_FILENAME)


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


def _get_tier_config(events: bool, continuous: bool) -> dict[str, Any]:
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
        ("tier", "data", "recordings_amount", "first_recording_id"),
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
        vis: MockViseron,
        tier: dict[str, Any],
        data: NDArray[Any],
        recordings_amount: Literal[2, 3],
        first_recording_id: Literal[3, 1],
    ) -> None:
        """Test _check_tier."""
        mock_camera = Mock()
        mock_camera.identifier = "test"
        mock_camera.config = {
            CONFIG_RECORDER: {
                CONFIG_LOOKBACK: 5,
                CONFIG_CONTINUOUS_RECORDING: True,
                CONFIG_SCHEDULE: None,
            }
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
        (
            "tiers_config",
            "recording_id",
            "force_delete",
            "next_tier_index",
            "move_thumbnail_called",
            "move_event_clip_called",
        ),
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
        tiers_config: list[dict[str, Any]],
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
            CONFIG_RECORDER: {
                CONFIG_LOOKBACK: 5,
                CONFIG_CONTINUOUS_RECORDING: True,
                CONFIG_SCHEDULE: None,
            }
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
        vis.data[STORAGE_COMPONENT].camera_tier_handlers = {  # type: ignore[misc]
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
            )
            if move_thumbnail_called:
                thumbnail_tier_handler.move_thumbnail.assert_called_once_with(
                    1, tier_handlers[next_tier_index].tier if next_tier_index else None
                )
            if move_event_clip_called:
                recordings_tier_handler.move_event_clip.assert_called_once_with(
                    1, tier_handlers[next_tier_index].tier if next_tier_index else None
                )


class TestCheckTierCallbackLifecycle:
    """Test that every check_tier request is matched by exactly one release."""

    def _make_tier_handler(self, vis: MockViseron) -> SegmentsTierHandler:
        mock_camera = Mock()
        mock_camera.identifier = "test"
        mock_camera.recorder.lookback = 5
        mock_camera.config = {
            CONFIG_RECORDER: {
                CONFIG_LOOKBACK: 5,
                CONFIG_CONTINUOUS_RECORDING: True,
                CONFIG_SCHEDULE: None,
            }
        }
        # _create_dataitem reads CONFIG_DRAIN, which _get_tier_config omits.
        tier_config = _get_tier_config(events=True, continuous=True)
        tier_config[CONFIG_DRAIN] = False

        tier_handler = SegmentsTierHandler(
            vis,
            mock_camera,
            0,
            "recorder",
            "segments",
            tier_config,
            None,
        )
        tier_handler._storage = Mock(spec=Storage)
        # No throttling, so only the in-flight guard can suppress a request.
        tier_handler._throttle_period = timedelta(0)
        tier_handler._time_of_last_call = utcnow() - timedelta(hours=1)
        return tier_handler

    def test_check_tier_sends_once_while_in_flight(self, vis: MockViseron) -> None:
        """Only one request is sent until the reply releases the slot."""
        tier_handler = self._make_tier_handler(vis)
        send = cast("Mock", tier_handler._storage.tier_check_worker_send_command)

        # Simulates the burst of file events seen during startup.
        for _ in range(50):
            tier_handler.check_tier()

        assert send.call_count == 1

    def test_no_op_reply_releases_slot(self, vis: MockViseron) -> None:
        """A reply with no data releases the slot and advances the throttle."""
        tier_handler = self._make_tier_handler(vis)
        send = cast("Mock", tier_handler._storage.tier_check_worker_send_command)

        tier_handler.check_tier()
        assert send.call_count == 1

        item = tier_handler._create_dataitem()
        item.data = None
        before = tier_handler._time_of_last_call
        tier_handler.on_check_tier_result(item)

        # Slot released and throttle advanced even though data was None.
        assert tier_handler._tier_check_in_progress is False
        assert tier_handler._time_of_last_call > before

        # A later event can now send again.
        tier_handler.check_tier()
        assert send.call_count == 2

    def test_empty_result_releases_slot_without_thread(self, vis: MockViseron) -> None:
        """An empty array releases the slot without spawning a worker thread."""
        tier_handler = self._make_tier_handler(vis)

        tier_handler.check_tier()
        item = tier_handler._create_dataitem()
        item.data = np.empty(0, dtype=[("id", np.int64)])

        with patch(
            "viseron.components.storage.tier_handler.RestartableThread"
        ) as mock_thread:
            tier_handler.on_check_tier_result(item)

        mock_thread.assert_not_called()
        assert tier_handler._tier_check_in_progress is False

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_slot_released_when_check_tier_raises(self, vis: MockViseron) -> None:
        """The slot is released even if processing the payload raises.

        The RuntimeError is raised on purpose inside the worker thread, so the
        resulting unhandled-thread-exception warning is expected.
        """
        tier_handler = self._make_tier_handler(vis)
        tier_handler.check_tier()

        item = tier_handler._create_dataitem()
        item.data = np.array(
            [(1, 1, "/tmp/test1.mp4", "/tmp/")],
            dtype=[
                ("recording_id", np.int64),
                ("id", np.int64),
                ("path", "U512"),
                ("tier_path", "U512"),
            ],
        )

        with patch.object(
            tier_handler, "_check_tier", side_effect=RuntimeError("boom")
        ):
            tier_handler.on_check_tier_result(item)
            # on_check_tier_result offloads to a thread; wait for it to finish.
            for thread in threading.enumerate():
                if thread.name.startswith("storage.tier_handler.check_tier."):
                    thread.join(timeout=5)

        assert tier_handler._tier_check_in_progress is False

    def test_slot_released_if_send_raises(self, vis: MockViseron) -> None:
        """The slot is released if the command never leaves the process."""
        tier_handler = self._make_tier_handler(vis)
        cast(
            "Mock", tier_handler._storage.tier_check_worker_send_command
        ).side_effect = RuntimeError("queue gone")

        with pytest.raises(RuntimeError):
            tier_handler.check_tier()

        assert tier_handler._tier_check_in_progress is False


def test_find_next_tier_segments(vis: Viseron):
    """Test find_next_tier_segments."""
    mock_storage = Mock(spec=Storage)
    mock_camera = Mock()
    mock_camera.identifier = "test_camera"
    mock_camera.config = {
        CONFIG_RECORDER: {
            CONFIG_LOOKBACK: 5,
            CONFIG_CONTINUOUS_RECORDING: True,
            CONFIG_SCHEDULE: None,
        }
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


def test_continuous_enabled_is_structural_only(vis: MockViseron) -> None:
    """continuous_enabled reflects config only, never live schedule state.

    The schedule is applied per-file inside the storage subprocess (see
    get_continuous_files_to_move), not by disabling the whole continuous
    retention path here.
    Disabling it here would route orphan continuous
    files through the events-only force_delete path and destroy already
    -retained footage the moment the schedule closes.
    """
    mock_camera = Mock()
    mock_camera.identifier = "test"
    mock_camera.recorder.lookback = 5
    mock_camera.config = {
        CONFIG_RECORDER: {
            CONFIG_LOOKBACK: 5,
            CONFIG_CONTINUOUS_RECORDING: True,
            CONFIG_SCHEDULE: {
                CONFIG_SCHEDULE_CONTINUOUS: [
                    {"start": "0 22 * * *", "end": "0 6 * * *"}
                ],
                CONFIG_SCHEDULE_TIMEZONE: "UTC",
            },
        }
    }

    tier = _get_tier_config(events=True, continuous=True)
    tier[CONFIG_DRAIN] = False
    tier_handler = SegmentsTierHandler(
        vis,
        mock_camera,
        0,
        "recorder",
        "segments",
        tier,
        None,
    )

    assert tier_handler.continuous_enabled is True
    assert tier_handler._create_dataitem().files_enabled is True


def test_create_dataitem_passes_continuous_schedule_entries(
    vis: MockViseron,
) -> None:
    """_create_dataitem forwards the configured continuous schedule and lookback."""
    mock_camera = Mock()
    mock_camera.identifier = "test"
    mock_camera.recorder.lookback = 7
    schedule_entries = [{"start": "0 22 * * *", "end": "0 6 * * *"}]
    mock_camera.config = {
        CONFIG_RECORDER: {
            CONFIG_LOOKBACK: 7,
            CONFIG_CONTINUOUS_RECORDING: True,
            CONFIG_SCHEDULE: {
                CONFIG_SCHEDULE_CONTINUOUS: schedule_entries,
                CONFIG_SCHEDULE_TIMEZONE: "Europe/Stockholm",
            },
        }
    }

    tier = _get_tier_config(events=True, continuous=True)
    tier[CONFIG_DRAIN] = False
    tier_handler = SegmentsTierHandler(
        vis,
        mock_camera,
        0,
        "recorder",
        "segments",
        tier,
        None,
    )

    item = tier_handler._create_dataitem()
    assert item.continuous_schedule == schedule_entries
    assert item.continuous_schedule_timezone == "Europe/Stockholm"
    assert item.continuous_lookback_seconds == 7


def test_create_dataitem_continuous_schedule_none_when_omitted(
    vis: MockViseron,
) -> None:
    """Omitting the schedule preserves the pre-existing always-on behavior."""
    mock_camera = Mock()
    mock_camera.identifier = "test"
    mock_camera.recorder.lookback = 5
    mock_camera.config = {
        CONFIG_RECORDER: {
            CONFIG_LOOKBACK: 5,
            CONFIG_CONTINUOUS_RECORDING: True,
            CONFIG_SCHEDULE: None,
        }
    }

    tier = _get_tier_config(events=True, continuous=True)
    tier[CONFIG_DRAIN] = False
    tier_handler = SegmentsTierHandler(
        vis,
        mock_camera,
        0,
        "recorder",
        "segments",
        tier,
        None,
    )

    assert tier_handler.continuous_enabled is True
    item = tier_handler._create_dataitem()
    assert item.continuous_schedule is None
    assert item.continuous_schedule_timezone is None
    assert item.files_enabled is True


def test_continuous_enabled_now_false_when_continuous_recording_disabled(
    vis: MockViseron,
) -> None:
    """continuous_recording: false still disables continuous regardless of schedule."""
    mock_camera = Mock()
    mock_camera.identifier = "test"
    mock_camera.config = {
        CONFIG_RECORDER: {
            CONFIG_LOOKBACK: 5,
            CONFIG_CONTINUOUS_RECORDING: False,
            CONFIG_SCHEDULE: None,
        }
    }

    tier_handler = SegmentsTierHandler(
        vis,
        mock_camera,
        0,
        "recorder",
        "segments",
        _get_tier_config(events=True, continuous=True),
        None,
    )

    assert tier_handler.continuous_enabled is False


def _make_bare_tier_handler(
    handler_class: type[_TierHandlerT],
    vis: MockViseron,
    storage: Mock,
    tier_id: int,
    tier_path: str,
    category: str,
    subcategory: str,
) -> _TierHandlerT:
    """Build a tier handler without starting its watchdog observer."""
    tier_handler = handler_class.__new__(handler_class)
    tier_handler._logger = logging.getLogger(__name__)
    tier_handler._vis = vis
    tier_handler._storage = storage
    tier_handler._camera = Mock(identifier="test")
    tier_handler._tier_id = tier_id
    tier_handler._tier = {CONFIG_PATH: tier_path}
    tier_handler._category = category
    tier_handler._subcategory = subcategory
    tier_handler.check_tier = Mock()  # type: ignore[method-assign]
    return tier_handler


@pytest.fixture(name="db_storage")
def fixture_db_storage(get_db_session: sessionmaker[Session]) -> Mock:
    """Storage mock backed by the test database."""
    storage = Mock(spec=Storage)
    storage.get_session = get_db_session
    storage.temporary_files_meta = {}
    storage.pending_moves = {}
    return storage


def _create_file(path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as file:
        file.write(b"data")
    return path


def _file_keys(storage: Mock) -> dict[str, int]:
    with storage.get_session() as session:
        rows = session.execute(select(Files.path, Files.file_key)).all()
    return {row.path: row.file_key for row in rows}


def _two_tiers(
    handler_class: type[_TierHandlerT],
    vis: MockViseron,
    storage: Mock,
    tmp_path: Path,
    category: str,
    subcategory: str,
) -> tuple[_TierHandlerT, _TierHandlerT]:
    return (
        _make_bare_tier_handler(
            handler_class,
            vis,
            storage,
            0,
            os.path.join(tmp_path, "tier0"),
            category,
            subcategory,
        ),
        _make_bare_tier_handler(
            handler_class,
            vis,
            storage,
            1,
            os.path.join(tmp_path, "tier1"),
            category,
            subcategory,
        ),
    )


def _tier_file(tier_handler: TierHandler, filename: str) -> str:
    return os.path.join(
        tier_handler.tier[CONFIG_PATH],
        tier_handler._category,
        tier_handler._subcategory,
        "test",
        filename,
    )


def _start_move(
    vis: MockViseron,
    storage: Mock,
    src_handler: TierHandler,
    dst_handler: TierHandler,
    filename: str,
) -> tuple[str, str]:
    """Run move_file, then replay the copy and delete done by the subprocess."""
    src = _tier_file(src_handler, filename)
    dst = _tier_file(dst_handler, filename)
    move_file(
        vis,
        storage,
        storage.get_session,
        "test",
        src_handler.tier_id,
        src_handler._category,
        src_handler._subcategory,
        src,
        dst,
        dst_handler.tier[CONFIG_PATH],
        logging.getLogger(__name__),
    )
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(src, dst)
    os.remove(src)
    return src, dst


def _simulate_move(
    vis: MockViseron,
    storage: Mock,
    src_handler: TierHandler,
    dst_handler: TierHandler,
    filename: str,
    observer_order: tuple[str, str],
) -> None:
    """Run a move and both observers.

    The source and destination observers drain separate event queues, so the
    order in which their callbacks run is not guaranteed.
    """
    src, dst = _start_move(vis, storage, src_handler, dst_handler, filename)
    observers = {
        "created": lambda: dst_handler._on_created(FileCreatedEvent(dst)),
        "deleted": lambda: src_handler._on_deleted(FileDeletedEvent(src)),
    }
    for observer in observer_order:
        observers[observer]()


OBSERVER_ORDERS = [
    pytest.param(("created", "deleted"), id="created_first"),
    pytest.param(("deleted", "created"), id="deleted_first"),
]


@pytest.mark.parametrize("observer_order", OBSERVER_ORDERS)
def test_file_key_survives_move(
    vis: MockViseron,
    db_storage: Mock,
    tmp_path: Path,
    observer_order: tuple[str, str],
) -> None:
    """Test that the destination row inherits the file_key of the source row."""
    tier0, tier1 = _two_tiers(
        TierHandler,
        vis,
        db_storage,
        tmp_path,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
    )
    src = _create_file(_tier_file(tier0, "1.m4s"))
    tier0._on_created(FileCreatedEvent(src))
    original_key = _file_keys(db_storage)[src]

    _simulate_move(vis, db_storage, tier0, tier1, "1.m4s", observer_order)

    assert _file_keys(db_storage) == {_tier_file(tier1, "1.m4s"): original_key}
    assert db_storage.temporary_files_meta == {}
    assert db_storage.pending_moves == {}


def test_file_key_resolvable_before_destination_is_observed(
    vis: MockViseron, db_storage: Mock, tmp_path: Path
) -> None:
    """Test that the key still resolves when the source row is deleted first.

    A polled destination tier can observe the new file seconds after the source
    tier observes the delete.
    """
    tier0, tier1 = _two_tiers(
        TierHandler,
        vis,
        db_storage,
        tmp_path,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
    )
    src = _create_file(_tier_file(tier0, "1.m4s"))
    tier0._on_created(FileCreatedEvent(src))
    original_key = _file_keys(db_storage)[src]

    src, dst = _start_move(vis, db_storage, tier0, tier1, "1.m4s")
    tier0._on_deleted(FileDeletedEvent(src))

    assert _file_keys(db_storage) == {dst: original_key}


@pytest.mark.parametrize("observer_order", OBSERVER_ORDERS)
def test_move_dispatches_file_created(
    vis: MockViseron,
    db_storage: Mock,
    tmp_path: Path,
    observer_order: tuple[str, str],
) -> None:
    """Test that the destination still announces the file once it is observed."""
    tier0, tier1 = _two_tiers(
        TierHandler,
        vis,
        db_storage,
        tmp_path,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
    )
    src = _create_file(_tier_file(tier0, "1.m4s"))
    tier0._on_created(FileCreatedEvent(src))
    vis.dispatch_event.reset_mock()

    _simulate_move(vis, db_storage, tier0, tier1, "1.m4s", observer_order)

    created_paths = [
        call.args[1].path
        for call in vis.dispatch_event.call_args_list
        if isinstance(call.args[1], EventFileCreated)
    ]
    assert created_paths == [_tier_file(tier1, "1.m4s")]


def test_failed_move_does_not_hand_over_row(
    vis: MockViseron, db_storage: Mock, tmp_path: Path
) -> None:
    """Test that the row is not moved to the destination after a failed move."""
    tier0, tier1 = _two_tiers(
        TierHandler,
        vis,
        db_storage,
        tmp_path,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
    )
    src = _create_file(_tier_file(tier0, "1.m4s"))
    tier0._on_created(FileCreatedEvent(src))
    dst = _tier_file(tier1, "1.m4s")

    move_file(
        vis,
        db_storage,
        db_storage.get_session,
        "test",
        0,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
        src,
        dst,
        tier1.tier[CONFIG_PATH],
        logging.getLogger(__name__),
    )
    callback = db_storage.tier_check_worker_send_command.call_args.kwargs["callback"]
    callback(DataItemMoveFile(cmd="move_file", src=src, dst=dst, error="boom"))
    # The source is later removed by something else, such as retention
    os.remove(src)
    tier0._on_deleted(FileDeletedEvent(src))

    assert not _file_keys(db_storage)


def test_new_files_get_distinct_file_keys(
    vis: MockViseron, db_storage: Mock, tmp_path: Path
) -> None:
    """Test that new files get fresh keys, including those with fragmenter meta."""
    tier0 = _make_bare_tier_handler(
        TierHandler,
        vis,
        db_storage,
        0,
        os.path.join(tmp_path, "tier0"),
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_SEGMENTS,
    )
    with_meta = _create_file(_tier_file(tier0, "1.m4s"))
    without_meta = _create_file(_tier_file(tier0, "2.m4s"))
    db_storage.temporary_files_meta[with_meta] = FilesMeta(
        orig_ctime=utcnow(), duration=5.0
    )

    tier0._on_created(FileCreatedEvent(with_meta))
    tier0._on_created(FileCreatedEvent(without_meta))

    keys = _file_keys(db_storage)
    assert set(keys) == {with_meta, without_meta}
    assert keys[with_meta] != keys[without_meta]
