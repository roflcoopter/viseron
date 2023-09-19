"""Test the TierHandler class."""

from dataclasses import dataclass
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import select

from viseron.components.storage.const import CONFIG_RECORDER
from viseron.components.storage.models import Recordings
from viseron.components.storage.tier_handler import RecorderTierHandler, handle_file
from viseron.domains.camera.const import CONFIG_LOOKBACK

from tests.common import BaseTestWithRecordings


@patch("viseron.components.storage.tier_handler.delete_file")
def test_handle_file_delete(
    mock_delete_file: Mock,
) -> None:
    """Test handle_file."""
    file = "/tmp/tier1/file1"
    tier_1 = {
        "path": "/tmp/tier1",
    }
    tier_2 = None
    session = MagicMock()
    handle_file(session, MagicMock(), "test", tier_1, tier_2, file)
    mock_delete_file.assert_called_once_with(session, file)


@patch("viseron.components.storage.tier_handler.move_file")
def test_handle_file_move(
    mock_move_file: Mock,
) -> None:
    """Test handle_file."""
    tier_1_file = "/tmp/tier1/file1"
    tier_2_file = "/tmp/tier2/file1"
    tier_1 = {
        "path": "/tmp/tier1",
    }
    tier_2 = {
        "path": "/tmp/tier2",
    }
    session = MagicMock()
    handle_file(session, MagicMock(), "test", tier_1, tier_2, tier_1_file)
    mock_move_file.assert_called_once_with(session, tier_1_file, tier_2_file)


@dataclass
class MockQueryResult:
    """Mock query result."""

    recording_id: int
    file_id: int
    path: str


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
            "min_age": {"minutes": max_age_continuous, "hours": None, "days": None},
            "max_size": {"gb": None, "mb": None},
            "max_age": {"minutes": None, "hours": None, "days": None},
            "min_size": {"gb": None, "mb": None},
        },
    }


class TestRecorderTierHandler(BaseTestWithRecordings):
    """Test the RecorderTierHandler class."""

    @pytest.mark.parametrize(
        (
            "tier, get_recordings_to_move_called, get_files_to_move_called,"
            "recordings_amount, first_recording_id"
        ),
        [
            (_get_tier_config(events=True, continuous=False), True, False, 1, 2),
            (_get_tier_config(events=True, continuous=True), True, True, 1, 2),
            (_get_tier_config(events=False, continuous=True), False, True, 2, 1),
        ],
    )
    def test__check_tier(
        self,
        vis,
        tier,
        get_recordings_to_move_called,
        get_files_to_move_called,
        recordings_amount,
        first_recording_id,
    ):
        """Test _check_tier."""

        mock_camera = Mock()
        mock_camera.identifier = "test_camera"
        mock_camera.config = {CONFIG_RECORDER: {CONFIG_LOOKBACK: 5}}

        tier_handler = RecorderTierHandler(
            vis,
            mock_camera,
            0,
            "recorder",
            "segments",
            tier,
            None,
        )

        with patch(
            "viseron.components.storage.tier_handler.get_recordings_to_move"
        ) as mock_get_recordings_to_move, patch(
            "viseron.components.storage.tier_handler.get_files_to_move"
        ) as mock_get_files_to_move, patch(
            "viseron.components.storage.tier_handler.files_to_move_overlap"
        ) as mock_files_to_move_overlap, patch(
            "viseron.components.storage.tier_handler.handle_file"
        ):
            mock_get_recordings_to_move.return_value = [
                MockQueryResult(1, 1, "/tmp/test1.mp4"),
                MockQueryResult(1, 2, "/tmp/test2.mp4"),
            ]
            mock_get_files_to_move.return_value = [
                MockQueryResult(1, 1, "/tmp/test1.mp4"),
                MockQueryResult(1, 2, "/tmp/test2.mp4"),
            ]
            tier_handler._check_tier(  # pylint: disable=protected-access
                self._get_db_session
            )
            if get_recordings_to_move_called:
                mock_get_recordings_to_move.assert_called_once()
            else:
                mock_get_recordings_to_move.assert_not_called()
            if get_files_to_move_called:
                mock_get_files_to_move.assert_called_once()
            else:
                mock_get_files_to_move.assert_not_called()
            if get_recordings_to_move_called and get_files_to_move_called:
                mock_files_to_move_overlap.assert_called_once()

        with self._get_db_session() as session:
            stmt = select(Recordings)
            recordings = session.execute(stmt).scalars().fetchall()
            assert len(recordings) == recordings_amount
            assert recordings[0].id == first_recording_id
