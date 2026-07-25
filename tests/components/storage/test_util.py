"""Test the util module."""

from collections import namedtuple
from unittest.mock import patch

from viseron.components.storage.util import (
    calculate_age,
    calculate_bytes,
    calculate_free_space_floor,
)

EventsFiles = namedtuple("EventsFiles", "recording_id file_id path")
ContinuousFiles = namedtuple("ContinuousFiles", "id path")

# 100 GiB total, so 15% == 15 GiB.
_DiskUsage = namedtuple("_DiskUsage", "total used free")
_FAKE_USAGE = _DiskUsage(total=100 * 1024**3, used=0, free=100 * 1024**3)


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


def test_calculate_free_space_floor_unset() -> None:
    """Unset (or empty) config disables free-space eviction."""
    assert calculate_free_space_floor(None, "/") == 0
    assert calculate_free_space_floor({}, "/") == 0
    assert (
        calculate_free_space_floor({"percent": None, "gb": None, "mb": None}, "/")
        == 0
    )


def test_calculate_free_space_floor_percent() -> None:
    """Percent is taken of the filesystem total."""
    with patch(
        "viseron.components.storage.util.shutil.disk_usage",
        return_value=_FAKE_USAGE,
    ):
        assert (
            calculate_free_space_floor(
                {"percent": 15, "gb": None, "mb": None}, "/data"
            )
            == 15 * 1024**3
        )


def test_calculate_free_space_floor_absolute() -> None:
    """Absolute gb/mb do not read the filesystem and are summed."""
    with patch(
        "viseron.components.storage.util.shutil.disk_usage"
    ) as mock_disk_usage:
        assert (
            calculate_free_space_floor({"percent": None, "gb": 40, "mb": None}, "/")
            == 40 * 1024**3
        )
        assert (
            calculate_free_space_floor({"percent": None, "gb": 1, "mb": 512}, "/")
            == 1024**3 + 512 * 1024**2
        )
        mock_disk_usage.assert_not_called()


def test_calculate_free_space_floor_max_of_several() -> None:
    """When several are set the largest (most conservative) floor wins."""
    with patch(
        "viseron.components.storage.util.shutil.disk_usage",
        return_value=_FAKE_USAGE,
    ):
        # percent -> 15 GiB, absolute -> 40 GiB => 40 GiB.
        assert (
            calculate_free_space_floor({"percent": 15, "gb": 40, "mb": None}, "/data")
            == 40 * 1024**3
        )
        # percent -> 15 GiB, absolute -> 5 GiB => 15 GiB.
        assert (
            calculate_free_space_floor({"percent": 15, "gb": 5, "mb": None}, "/data")
            == 15 * 1024**3
        )


def test_calculate_free_space_floor_stat_failure() -> None:
    """A failing stat drops the percent term but keeps the absolute floor."""
    with patch(
        "viseron.components.storage.util.shutil.disk_usage",
        side_effect=OSError("no such path"),
    ):
        assert (
            calculate_free_space_floor(
                {"percent": 15, "gb": 10, "mb": None}, "/missing"
            )
            == 10 * 1024**3
        )
        assert (
            calculate_free_space_floor(
                {"percent": 15, "gb": None, "mb": None}, "/missing"
            )
            == 0
        )
