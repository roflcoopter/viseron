"""Tests for __main__.py."""
# import logging
from unittest.mock import MagicMock, patch

import pytest

import viseron.__main__


@pytest.fixture
def mocked_viseron(mocker):
    """Mock Viseron class."""
    mocker.patch("viseron.__main__.Viseron", return_value="Testing")


def test_init(simple_config, mocked_viseron):
    """Test init."""
    viseron.__main__.main()
    # viseron.__main__.LOGGER.info("testing")
    with patch.object(viseron.__main__, "main", MagicMock()) as mock_main:
        with patch.object(viseron.__main__, "__name__", "__main__"):
            viseron.__main__.init()
    mock_main.assert_called_once()


# class TestMyFormatter:
#     """Tests for class MyFormatter."""

#     def test_format(self):
#         """Test formatter."""
#         formatter = viseron.__main__.MyFormatter()
#         record = logging.makeLogRecord(
#             {
#                 "name": "test_logger",
#                 "level": 10,
#                 "pathname": "test_main.py",
#                 "msg": "Testing, message repeated 2 times",
#             }
#         )
#         formatter.format(record)
