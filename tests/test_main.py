"""Tests for __main__.py."""
from unittest.mock import MagicMock, patch

import pytest

import viseron.__main__


@pytest.fixture
def mocked_viseron(mocker):
    """Mock Viseron class."""
    mocker.patch("viseron.__main__.setup_viseron", return_value="Testing")


def test_init(simple_config, mocked_viseron):
    """Test init."""
    viseron.__main__.main()
    with patch.object(viseron.__main__, "main", MagicMock()) as mock_main:
        with patch.object(viseron.__main__, "__name__", "__main__"):
            viseron.__main__.init()
    mock_main.assert_called_once()
