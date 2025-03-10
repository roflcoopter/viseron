"""Test helpers module."""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import pytest

from viseron import helpers


@pytest.mark.parametrize(
    "frame_res, model_res, bbox, expected, raises, message",
    [
        (
            (1920, 1080),
            (300, 300),
            (75, 90, 105, 120),
            (0.25, 0.144, 0.35, 0.322),
            nullcontext(),
            None,
        ),
        (
            (1080, 1920),
            (300, 300),
            (75, 90, 105, 120),
            (0.056, 0.3, 0.233, 0.4),
            nullcontext(),
            None,
        ),
        (
            (640, 360),
            (640, 640),
            (10, 320, 10, 320),
            (0.016, 0.5, 0.016, 0.5),
            nullcontext(),
            None,
        ),
        (
            (640, 360),
            (640, 640),
            (10, 140, 10, 140),
            (0.016, 0.0, 0.016, 0.0),
            nullcontext(),
            None,
        ),
        (
            (360, 640),
            (640, 640),
            (320, 5, 320, 5),
            (0.5, 0.008, 0.5, 0.008),
            nullcontext(),
            None,
        ),
        (
            (360, 640),
            (640, 640),
            (140, 5, 140, 5),
            (0.0, 0.008, 0.0, 0.008),
            nullcontext(),
            None,
        ),
        (
            (0, 0),
            (600, 640),
            (0, 0, 0, 0),
            (0, 0, 0, 0),
            pytest.raises(ValueError),
            (
                "Can only convert bbox from a letterboxed image "
                "for models of equal width and height, got 600x640"
            ),
        ),
    ],
)
def test_convert_letterboxed_bbox(
    frame_res, model_res, bbox, expected, raises, message
):
    """Test convert_letterboxed_bbox."""
    with raises as exception:
        converted_bbox = helpers.convert_letterboxed_bbox(
            frame_res[0], frame_res[1], model_res[0], model_res[1], bbox
        )
        assert converted_bbox == expected
    if message:
        assert str(exception.value) == message


def test_basic_conversion_zero_offset():
    """Test with zero UTC offset."""
    date = "2024-01-01"
    utc_offset = timedelta(hours=0)

    time_from, time_to = helpers.daterange_to_utc(date, utc_offset)

    assert time_from == datetime(2024, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
    assert time_to == datetime(2024, 1, 1, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_positive_utc_offset():
    """Test with positive UTC offset (e.g., UTC+5)."""
    date = "2024-01-01"
    utc_offset = timedelta(hours=5)

    time_from, time_to = helpers.daterange_to_utc(date, utc_offset)

    # With UTC+5, the UTC time should be 5 hours earlier
    assert time_from == datetime(2023, 12, 31, 19, 0, 0, 0, tzinfo=timezone.utc)
    assert time_to == datetime(2024, 1, 1, 18, 59, 59, 999999, tzinfo=timezone.utc)


def test_negative_utc_offset():
    """Test with negative UTC offset (e.g., UTC-5)."""
    date = "2024-01-01"
    utc_offset = timedelta(hours=-5)

    time_from, time_to = helpers.daterange_to_utc(date, utc_offset)

    # With UTC-5, the UTC time should be 5 hours later
    assert time_from == datetime(2024, 1, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
    assert time_to == datetime(2024, 1, 2, 4, 59, 59, 999999, tzinfo=timezone.utc)


def test_fractional_hour_offset():
    """Test with UTC offset including minutes."""
    date = "2024-01-01"
    utc_offset = timedelta(hours=5, minutes=30)  # UTC+5:30 (like India)

    time_from, time_to = helpers.daterange_to_utc(date, utc_offset)

    assert time_from == datetime(2023, 12, 31, 18, 30, 0, 0, tzinfo=timezone.utc)
    assert time_to == datetime(2024, 1, 1, 18, 29, 59, 999999, tzinfo=timezone.utc)


def test_year_boundary():
    """Test date at year boundary with offset that crosses the year."""
    date = "2024-01-01"
    utc_offset = timedelta(hours=2)

    time_from, time_to = helpers.daterange_to_utc(date, utc_offset)

    assert time_from == datetime(2023, 12, 31, 22, 0, 0, 0, tzinfo=timezone.utc)
    assert time_to == datetime(2024, 1, 1, 21, 59, 59, 999999, tzinfo=timezone.utc)


def test_invalid_date_format():
    """Test that invalid date format raises ValueError."""
    date = "2024/01/01"  # Wrong format
    utc_offset = timedelta(hours=0)

    with pytest.raises(ValueError):
        helpers.daterange_to_utc(date, utc_offset)


def test_leap_year_date():
    """Test with February 29th on a leap year."""
    date = "2024-02-29"  # 2024 is a leap year
    utc_offset = timedelta(hours=0)

    time_from, time_to = helpers.daterange_to_utc(date, utc_offset)

    assert time_from == datetime(2024, 2, 29, 0, 0, 0, 0, tzinfo=timezone.utc)
    assert time_to == datetime(2024, 2, 29, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_extreme_offset():
    """Test with maximum possible UTC offset."""
    date = "2024-01-01"
    utc_offset = timedelta(hours=14)  # Maximum UTC offset (UTC+14)

    time_from, time_to = helpers.daterange_to_utc(date, utc_offset)

    assert time_from == datetime(2023, 12, 31, 10, 0, 0, 0, tzinfo=timezone.utc)
    assert time_to == datetime(2024, 1, 1, 9, 59, 59, 999999, tzinfo=timezone.utc)


def test_microsecond_precision():
    """Test that microsecond precision is maintained."""
    date = "2024-01-01"
    utc_offset = timedelta(hours=0)

    time_from, time_to = helpers.daterange_to_utc(date, utc_offset)

    assert time_from.microsecond == 0
    assert time_to.microsecond == 999999
