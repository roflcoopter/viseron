"""Test the util module."""

import errno
import os
from collections import namedtuple
from unittest.mock import patch

import pytest

from viseron.components.storage.util import (
    calculate_age,
    calculate_bytes,
    is_transient_filesystem_error,
    path_exists,
    tier_path_available,
)

EventsFiles = namedtuple("EventsFiles", "recording_id file_id path")
ContinuousFiles = namedtuple("ContinuousFiles", "id path")


def test_calculate_bytes() -> None:
    """Test calculate_bytes."""
    assert calculate_bytes({"mb": 1, "gb": None}) == 1048576
    assert calculate_bytes({"mb": None, "gb": 1}) == 1073741824
    assert calculate_bytes({"mb": 0, "gb": 2}) == 2147483648
    assert calculate_bytes({"mb": 2, "gb": 2}) == 2097152 + 2147483648


def test_calculate_age() -> None:
    """Test calculate_age."""
    assert (
        calculate_age({"minutes": 1, "days": None, "hours": None}).total_seconds() == 60
    )
    assert (
        calculate_age({"minutes": None, "days": 1, "hours": None}).total_seconds()
        == 86400
    )
    assert (
        calculate_age({"minutes": None, "days": None, "hours": 1}).total_seconds()
        == 3600
    )
    assert calculate_age({"minutes": 1, "days": 1, "hours": 1}).total_seconds() == 90060


def test_is_transient_filesystem_error() -> None:
    """Test transient filesystem error detection."""
    assert is_transient_filesystem_error(OSError(errno.ETIMEDOUT, "timed out"))
    assert is_transient_filesystem_error(
        OSError(errno.ECONNABORTED, "connection aborted")
    )
    assert not is_transient_filesystem_error(FileNotFoundError())
    assert not is_transient_filesystem_error(OSError(errno.ENOSPC, "no space left"))


def test_path_exists_propagates_transient_errors() -> None:
    """Test path_exists does not treat remote filesystem errors as missing."""
    with patch("os.stat", side_effect=OSError(errno.EIO, "io error")):
        with pytest.raises(OSError):
            path_exists("/remote/file")


def test_tier_path_available_uses_stat_not_scandir() -> None:
    """Test tier_path_available avoids directory enumeration."""
    stat_result = os.stat_result((0o040755, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    with (
        patch("os.stat", return_value=stat_result) as stat_mock,
        patch("os.scandir") as scandir_mock,
    ):
        assert tier_path_available("/remote/tier")

    stat_mock.assert_called_once_with("/remote/tier")
    scandir_mock.assert_not_called()
