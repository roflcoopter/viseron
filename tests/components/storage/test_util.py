"""Test the util module."""

from viseron.components.storage.util import calculate_age, calculate_bytes


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
