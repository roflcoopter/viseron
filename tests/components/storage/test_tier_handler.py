"""Test the TierHandler class."""

import threading
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal, cast
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
from numpy._typing._array_like import NDArray
from sqlalchemy import select

from viseron import Viseron
from viseron.components.storage import Storage
from viseron.components.storage.const import (
    COMPONENT as STORAGE_COMPONENT,
    CONFIG_DRAIN,
    CONFIG_RECORDER,
    LATEST_SNAPSHOT_FILENAME,
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
)
from viseron.components.storage.models import Recordings
from viseron.components.storage.tier_handler import (
    EventClipTierHandler,
    SegmentsTierHandler,
    SnapshotTierHandler,
    ThumbnailTierHandler,
    TierHandler,
    find_next_tier_segments,
    handle_file,
)
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
