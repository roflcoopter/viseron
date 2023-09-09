"""Test the TierHandler class."""

from unittest.mock import MagicMock, Mock, patch

from viseron.components.storage.tier_handler import handle_file


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
