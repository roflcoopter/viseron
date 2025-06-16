"""Test the TierHandler class."""

from dataclasses import dataclass
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
from sqlalchemy import select

from viseron import Viseron
from viseron.components.storage import Storage
from viseron.components.storage.const import (
    COMPONENT as STORAGE_COMPONENT,
    CONFIG_RECORDER,
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
)
from viseron.components.storage.models import Recordings
from viseron.components.storage.tier_handler import (
    EventClipTierHandler,
    SegmentsTierHandler,
    ThumbnailTierHandler,
    find_next_tier_segments,
    handle_file,
)
from viseron.domains.camera.const import CONFIG_CONTINUOUS_RECORDING, CONFIG_LOOKBACK

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
    handle_file(
        vis,
        session,
        MagicMock(),
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
    mock_delete_file.assert_called_once_with(session, file, logger)


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
            tier_handler._check_tier(  # pylint: disable=protected-access
                self._get_db_session, data
            )

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
            tier_handlers[0]._check_tier(  # pylint: disable=protected-access
                self._get_db_session, data
            )
            mock_handle_file.assert_called_once_with(
                tier_handlers[0]._vis,  # pylint: disable=protected-access
                self._get_db_session,
                tier_handlers[0]._storage,  # pylint: disable=protected-access
                tier_handlers[0]._camera.identifier,  # pylint: disable=protected-access
                tier_handlers[0].tier_id,
                TIER_CATEGORY_RECORDER,
                TIER_SUBCATEGORY_SEGMENTS,
                tier_handlers[0].tier,
                tier_handlers[next_tier_index].tier if next_tier_index else None,
                "/tmp/test1.mp4",
                "/tmp/",
                tier_handlers[0]._logger,  # pylint: disable=protected-access
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
