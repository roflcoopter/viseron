"""Test the Logger API handler."""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest

from viseron.components.webserver.api.v1.logger import _parse_log_line


@pytest.fixture
def helsinki_tz(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run the test with the server's local timezone set to Europe/Helsinki."""
    monkeypatch.setenv("TZ", "Europe/Helsinki")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.mark.usefixtures("helsinki_tz")
@pytest.mark.parametrize(
    ("timestamp", "expected_unix_ms"),
    [
        # Winter time, EET (UTC+2)
        ("2026-11-18 12:54:37.194", 1794999277194),
        # Summer time, EEST (UTC+3)
        ("2026-07-01 12:00:00.000", 1782896400000),
    ],
)
def test_parse_log_line_timestamp_uses_local_offset_of_date(
    timestamp: str, expected_unix_ms: int
) -> None:
    """Test that the UTC offset in effect on the log line's date is used."""
    line = f"{timestamp} [INFO    ] [viseron.core] - Viseron initialized"
    parsed = _parse_log_line(line, 0)
    assert parsed["timestamp"] == timestamp
    assert parsed["timestamp_unix_ms"] == expected_unix_ms
