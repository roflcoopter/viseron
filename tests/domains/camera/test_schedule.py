"""Tests for camera recording schedule evaluation."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import patch

import pytest
from croniter import croniter

from viseron.domains.camera.const import CONFIG_SCHEDULE_TIMEZONE
from viseron.domains.camera.schedule import (
    _schedule_active_at_minute,
    resolve_timezone,
    schedule_active,
    schedule_state_changes,
)
from viseron.helpers import get_local_timezone
from viseron.helpers.validators import UNDEFINED

WEEKDAY_EVENING = datetime.datetime(
    2024, 1, 1, 20, 0, tzinfo=datetime.timezone.utc
)  # Monday
WEEKDAY_MORNING = datetime.datetime(
    2024, 1, 1, 10, 0, tzinfo=datetime.timezone.utc
)  # Monday
WEEKEND_MORNING = datetime.datetime(
    2024, 1, 6, 10, 0, tzinfo=datetime.timezone.utc
)  # Saturday

WEEKDAY_SCHEDULE = [{"start": "0 8 * * mon-fri", "end": "0 18 * * mon-fri"}]
OVERNIGHT_SCHEDULE = [{"start": "0 22 * * *", "end": "0 6 * * *"}]


@pytest.mark.parametrize("entries", [None, []])
def test_schedule_active_no_entries(entries: list[dict[str, Any]] | None) -> None:
    """No entries means recording is never restricted."""
    assert schedule_active(entries, "UTC", WEEKDAY_EVENING) is True


def test_schedule_active_within_window() -> None:
    """Active during a same-day window on a matching weekday."""
    assert schedule_active(WEEKDAY_SCHEDULE, "UTC", WEEKDAY_MORNING) is True


def test_schedule_active_outside_window() -> None:
    """Inactive outside the configured hours on a matching weekday."""
    assert schedule_active(WEEKDAY_SCHEDULE, "UTC", WEEKDAY_EVENING) is False


def test_schedule_active_wrong_day() -> None:
    """Inactive on a day of week not covered by the cron expression."""
    assert schedule_active(WEEKDAY_SCHEDULE, "UTC", WEEKEND_MORNING) is False


def test_schedule_active_overnight_before_midnight() -> None:
    """Overnight window is active before midnight on the start day."""
    before_midnight = datetime.datetime(2024, 1, 1, 23, 0, tzinfo=datetime.timezone.utc)
    assert schedule_active(OVERNIGHT_SCHEDULE, "UTC", before_midnight) is True


def test_schedule_active_overnight_after_midnight() -> None:
    """Overnight window is still active just after midnight on the next day."""
    after_midnight = datetime.datetime(2024, 1, 2, 3, 0, tzinfo=datetime.timezone.utc)
    assert schedule_active(OVERNIGHT_SCHEDULE, "UTC", after_midnight) is True


def test_schedule_active_overnight_daytime() -> None:
    """Overnight window is inactive during the following day."""
    daytime = datetime.datetime(2024, 1, 2, 12, 0, tzinfo=datetime.timezone.utc)
    assert schedule_active(OVERNIGHT_SCHEDULE, "UTC", daytime) is False


def test_schedule_active_multiple_entries_ored() -> None:
    """Any matching entry makes the schedule active."""
    entries = [
        {"start": "0 8 * * mon-fri", "end": "0 18 * * mon-fri"},
        {"start": "0 0 * * sat,sun", "end": "59 23 * * sat,sun"},
    ]
    assert schedule_active(entries, "UTC", WEEKEND_MORNING) is True
    assert schedule_active(entries, "UTC", WEEKDAY_MORNING) is True
    assert schedule_active(entries, "UTC", WEEKDAY_EVENING) is False


def test_schedule_active_defaults_to_now() -> None:
    """Now defaults to the current system time when not provided."""
    assert schedule_active(None, "UTC") is True


def test_schedule_active_inclusive_of_start_boundary() -> None:
    """The window is active at the exact minute the start cron fires."""
    entries = [{"start": "0 8 * * *", "end": "0 18 * * *"}]
    at_start = datetime.datetime(2024, 1, 1, 8, 0, tzinfo=datetime.timezone.utc)
    assert schedule_active(entries, "UTC", at_start) is True


def test_schedule_active_exclusive_of_end_boundary() -> None:
    """The window is no longer active at the exact minute the end cron fires."""
    entries = [{"start": "0 8 * * *", "end": "0 18 * * *"}]
    at_end = datetime.datetime(2024, 1, 1, 18, 0, tzinfo=datetime.timezone.utc)
    assert schedule_active(entries, "UTC", at_end) is False


def test_schedule_active_respects_non_utc_timezone() -> None:
    """A UTC instant is evaluated against the configured zone's wall clock."""
    entries = [{"start": "0 8 * * *", "end": "0 18 * * *"}]
    at_07_30_utc = datetime.datetime(2024, 1, 1, 7, 30, tzinfo=datetime.timezone.utc)
    assert schedule_active(entries, "UTC", at_07_30_utc) is False
    assert schedule_active(entries, "Europe/Stockholm", at_07_30_utc) is True


def test_schedule_active_timezone_across_dst_transition() -> None:
    """The configured zone's DST offset is respected, not a fixed UTC offset."""
    entries = [{"start": "0 8 * * *", "end": "0 18 * * *"}]

    winter_06_30_utc = datetime.datetime(
        2024, 1, 1, 6, 30, tzinfo=datetime.timezone.utc
    )
    assert schedule_active(entries, "Europe/Stockholm", winter_06_30_utc) is False

    summer_06_30_utc = datetime.datetime(
        2024, 7, 1, 6, 30, tzinfo=datetime.timezone.utc
    )
    assert schedule_active(entries, "Europe/Stockholm", summer_06_30_utc) is True


class TestScheduleActiveCaching:
    """Tests for the per-minute memoization of schedule_active.

    schedule_active is called for every frame the NVR processes, and cron
    expressions only change state on minute boundaries, so the answer is cached
    for the minute it was computed in.
    """

    SCHEDULE = [{"start": "0 8 * * *", "end": "0 18 * * *"}]

    def setup_method(self) -> None:
        """Clear the lru_cache before each test."""
        _schedule_active_at_minute.cache_clear()

    def teardown_method(self) -> None:
        """Clear the lru_cache after each test."""
        _schedule_active_at_minute.cache_clear()

    def test_repeated_calls_within_the_same_minute_parse_cron_once(self) -> None:
        """Cron expressions are parsed once per minute, not once per call."""
        now = datetime.datetime(2024, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)

        with patch(
            "viseron.domains.camera.schedule.croniter", wraps=croniter
        ) as mock_croniter:
            for second in range(0, 60, 5):
                assert (
                    schedule_active(self.SCHEDULE, "UTC", now.replace(second=second))
                    is True
                )

        # One croniter per cron expression, for the first call only
        assert mock_croniter.call_count == 2

    def test_cache_is_keyed_per_minute(self) -> None:
        """The cached answer expires on the minute the schedule flips."""
        just_before_end = datetime.datetime(
            2024, 1, 1, 17, 59, 59, tzinfo=datetime.timezone.utc
        )
        at_end = datetime.datetime(2024, 1, 1, 18, 0, tzinfo=datetime.timezone.utc)

        assert schedule_active(self.SCHEDULE, "UTC", just_before_end) is True
        assert schedule_active(self.SCHEDULE, "UTC", at_end) is False

    def test_cache_is_keyed_on_entries_and_timezone(self) -> None:
        """Different schedules and timezones must not share a cache entry."""
        at_07_30_utc = datetime.datetime(
            2024, 1, 1, 7, 30, tzinfo=datetime.timezone.utc
        )

        assert schedule_active(self.SCHEDULE, "UTC", at_07_30_utc) is False
        assert schedule_active(self.SCHEDULE, "Europe/Stockholm", at_07_30_utc) is True
        assert (
            schedule_active(
                [{"start": "0 7 * * *", "end": "0 18 * * *"}], "UTC", at_07_30_utc
            )
            is True
        )


class TestScheduleStateChanges:
    """Tests for schedule_state_changes."""

    SCHEDULE = [{"start": "0 8 * * *", "end": "0 18 * * *"}]

    def test_range_inside_a_window_has_no_changes(self) -> None:
        """A range that never crosses a cron firing is a single state."""
        start = datetime.datetime(2024, 1, 1, 9, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2024, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)

        assert schedule_state_changes(self.SCHEDULE, "UTC", start, end) == [
            (start.timestamp(), True)
        ]

    def test_window_boundaries_are_reported(self) -> None:
        """Both edges of a window show up as state changes."""
        start = datetime.datetime(2024, 1, 1, 7, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2024, 1, 1, 19, 0, tzinfo=datetime.timezone.utc)

        assert schedule_state_changes(self.SCHEDULE, "UTC", start, end) == [
            (start.timestamp(), False),
            (
                datetime.datetime(
                    2024, 1, 1, 8, 0, tzinfo=datetime.timezone.utc
                ).timestamp(),
                True,
            ),
            (
                datetime.datetime(
                    2024, 1, 1, 18, 0, tzinfo=datetime.timezone.utc
                ).timestamp(),
                False,
            ),
        ]

    def test_firings_that_do_not_flip_the_state_are_collapsed(self) -> None:
        """Overlapping entries only produce a change where the union changes."""
        entries = [
            {"start": "0 8 * * *", "end": "0 18 * * *"},
            {"start": "0 9 * * *", "end": "0 17 * * *"},
        ]
        start = datetime.datetime(2024, 1, 1, 7, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2024, 1, 1, 19, 0, tzinfo=datetime.timezone.utc)

        changes = schedule_state_changes(entries, "UTC", start, end)

        # 09:00 and 17:00 fire but the union is unchanged there
        assert [active for _, active in changes] == [False, True, False]

    def test_changes_are_evaluated_in_the_configured_timezone(self) -> None:
        """Cron fields are matched against the configured zone's wall clock."""
        start = datetime.datetime(2024, 1, 1, 5, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2024, 1, 1, 19, 0, tzinfo=datetime.timezone.utc)

        changes = schedule_state_changes(self.SCHEDULE, "Europe/Stockholm", start, end)

        # Stockholm is UTC+1 in January
        assert changes == [
            (start.timestamp(), False),
            (
                datetime.datetime(
                    2024, 1, 1, 7, 0, tzinfo=datetime.timezone.utc
                ).timestamp(),
                True,
            ),
            (
                datetime.datetime(
                    2024, 1, 1, 17, 0, tzinfo=datetime.timezone.utc
                ).timestamp(),
                False,
            ),
        ]

    def test_max_changes_truncates_a_too_fine_grained_schedule(self) -> None:
        """The walk stops once max_changes is exceeded.

        A schedule that flips every minute has nothing to collapse, so callers
        that only need to know it is unenumerable can cap the work.
        """
        # Active on even minutes, inactive on odd ones
        entries = [{"start": "*/2 * * * *", "end": "1-59/2 * * * *"}]
        start = datetime.datetime(2024, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
        end = start + datetime.timedelta(hours=1)

        assert len(schedule_state_changes(entries, "UTC", start, end)) == 61
        assert (
            len(schedule_state_changes(entries, "UTC", start, end, max_changes=5)) == 6
        )

    def test_matches_a_per_instant_evaluation(self) -> None:
        """The bisected result is identical to evaluating every minute."""
        start = datetime.datetime(2024, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
        end = start + datetime.timedelta(days=2)

        changes = schedule_state_changes(self.SCHEDULE, "UTC", start, end)

        minute = start
        while minute <= end:
            index = max(
                i for i, (ts, _) in enumerate(changes) if ts <= minute.timestamp()
            )
            assert changes[index][1] == schedule_active(self.SCHEDULE, "UTC", minute)
            minute += datetime.timedelta(minutes=17)


class TestResolveTimezone:
    """Tests for resolve_timezone."""

    def setup_method(self):
        """Clear the lru_cache before each test."""
        get_local_timezone.cache_clear()

    def teardown_method(self):
        """Clear the lru_cache after each test."""
        get_local_timezone.cache_clear()

    @pytest.mark.parametrize("configured", [UNDEFINED, None])
    def test_unset_resolves_to_server_timezone(self, configured) -> None:
        """An unset timezone is resolved to the server's timezone at runtime."""
        schedule = {CONFIG_SCHEDULE_TIMEZONE: configured}
        with patch(
            "viseron.domains.camera.schedule.get_local_timezone",
            return_value="Europe/Stockholm",
        ):
            assert resolve_timezone(schedule) == "Europe/Stockholm"

    def test_missing_key_resolves_to_server_timezone(self) -> None:
        """A schedule without the key at all still resolves."""
        with patch(
            "viseron.domains.camera.schedule.get_local_timezone",
            return_value="Europe/Stockholm",
        ):
            assert resolve_timezone({}) == "Europe/Stockholm"

    def test_explicit_timezone_is_used_verbatim(self) -> None:
        """An explicitly configured timezone overrides the server default."""
        schedule = {CONFIG_SCHEDULE_TIMEZONE: "America/New_York"}
        with patch(
            "viseron.domains.camera.schedule.get_local_timezone",
            return_value="Europe/Stockholm",
        ):
            assert resolve_timezone(schedule) == "America/New_York"
