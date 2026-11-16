"""Tests for viseron.helpers.json."""

import datetime
import json

from viseron.helpers.json import JSONEncoder


def test_naive_datetime_is_serialized_as_utc():
    """A naive datetime is treated as UTC."""
    value = datetime.datetime(2024, 1, 1, 12, 0, 0)
    encoded = json.loads(json.dumps({"t": value}, cls=JSONEncoder))
    assert encoded["t"] == "2024-01-01T12:00:00+00:00"


def test_utc_datetime_is_serialized_unchanged():
    """A UTC datetime keeps its wall clock time."""
    value = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    encoded = json.loads(json.dumps({"t": value}, cls=JSONEncoder))
    assert encoded["t"] == "2024-01-01T12:00:00+00:00"


def test_non_utc_datetime_is_converted_to_utc():
    """An aware datetime in another timezone must be converted, not relabeled.

    12:00+02:00 is 10:00 UTC. replace(tzinfo=utc) used to keep the wall clock
    value and only swap the offset, shifting every non-UTC timestamp by its
    own UTC offset when serialized.
    """
    tz = datetime.timezone(datetime.timedelta(hours=2))
    value = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz)
    encoded = json.loads(json.dumps({"t": value}, cls=JSONEncoder))
    assert encoded["t"] == "2024-01-01T10:00:00+00:00"
