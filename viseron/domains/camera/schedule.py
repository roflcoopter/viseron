"""Recording schedule evaluation."""

from __future__ import annotations

import datetime
import functools
from typing import Any, cast
from zoneinfo import ZoneInfo

from croniter import croniter

from viseron.helpers import get_local_timezone, utcnow
from viseron.helpers.validators import UNDEFINED

from .const import (
    CONFIG_SCHEDULE_END,
    CONFIG_SCHEDULE_START,
    CONFIG_SCHEDULE_TIMEZONE,
)

# Each schedule entry as the (start, end) pair of cron expressions, which is all
# that is needed to evaluate it and is hashable so it can key the cache.
ScheduleKey = tuple[tuple[str, str], ...]


def _entry_active(entry: tuple[str, str], now: datetime.datetime) -> bool:
    """Return if a single schedule entry is currently active.

    croniter.get_prev() is exclusive, so `now` is nudged by one second to make it
    inclusive.
    """
    start_expression, end_expression = entry
    inclusive_now = now + datetime.timedelta(seconds=1)
    start_prev = croniter(start_expression, inclusive_now).get_prev(datetime.datetime)
    end_prev = croniter(end_expression, inclusive_now).get_prev(datetime.datetime)
    return start_prev > end_prev


def _schedule_key(entries: list[dict[str, Any]]) -> ScheduleKey:
    """Return the hashable cache key for a list of schedule entries."""
    return tuple(
        (entry[CONFIG_SCHEDULE_START], entry[CONFIG_SCHEDULE_END]) for entry in entries
    )


@functools.lru_cache(maxsize=256)
def _schedule_active_at_minute(
    entries: ScheduleKey, timezone: str, minute: int
) -> bool:
    """Return if the schedule is active during the given minute of the epoch.

    Cron says nothing finer than a minute, so every instant within the same
    minute has the same answer and only the first one has to be computed. That
    matters because the NVR asks per frame, and each miss parses two cron
    expressions per entry.

    The cron expressions and the timezone are part of the cache key, so a
    reloaded config never reads a stale answer.
    """
    now = datetime.datetime.fromtimestamp(
        minute * 60, tz=datetime.timezone.utc
    ).astimezone(ZoneInfo(timezone))
    return any(_entry_active(entry, now) for entry in entries)


def resolve_timezone(schedule: dict[str, Any]) -> str:
    """Return the timezone a schedule's cron expressions are evaluated in."""
    timezone = schedule.get(CONFIG_SCHEDULE_TIMEZONE)
    if not timezone or timezone is UNDEFINED:
        return get_local_timezone()
    return cast("str", timezone)


def schedule_active(
    entries: list[dict[str, Any]] | None | type[UNDEFINED],
    timezone: str,
    now: datetime.datetime | None = None,
) -> bool:
    """Return if recording should be active according to the schedule.

    A None/UNDEFINED/empty list of entries means there is no restriction, so
    recording is always considered active.

    `now` is converted to `timezone` before evaluation, so cron fields are
    matched against that zone's wall-clock time (DST-aware) rather than UTC.
    """
    if not entries or entries == UNDEFINED:
        return True
    resolved_entries = cast("list[dict[str, Any]]", entries)

    now = now or utcnow()
    return _schedule_active_at_minute(
        _schedule_key(resolved_entries), timezone, int(now.timestamp()) // 60
    )


def schedule_state_changes(
    entries: list[dict[str, Any]],
    timezone: str,
    start: datetime.datetime,
    end: datetime.datetime,
    max_changes: int | None = None,
) -> list[tuple[float, bool]]:
    """Return when the schedule turns on and off between start and end.

    The first pair is `start` and the state at `start`, and every pair after it
    is a point where the state flips, so an 08:00-18:00 schedule over one day
    reads as [(00:00, False), (08:00, True), (18:00, False)]. Bisect on the
    timestamps to resolve any instant in the range.

    A schedule can only flip when one of its cron expressions fires, so this
    costs a handful of evaluations no matter how many instants are looked up.

    `max_changes` stops the walk early, for callers that only need to know the
    schedule is too fine-grained to enumerate. The returned list is longer than
    `max_changes` when that happened.
    """
    zone = ZoneInfo(timezone)
    start = start.astimezone(zone)
    end = end.astimezone(zone)

    firings: set[float] = set()
    for entry in _schedule_key(entries):
        for expression in entry:
            iterator = croniter(expression, start)
            while (firing := iterator.get_next(datetime.datetime)) <= end:
                firings.add(firing.timestamp())

    changes = [(start.timestamp(), schedule_active(entries, timezone, start))]
    for timestamp in sorted(firings):
        active = schedule_active(
            entries,
            timezone,
            datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc),
        )
        if active is not changes[-1][1]:
            changes.append((timestamp, active))
            if max_changes is not None and len(changes) > max_changes:
                break
    return changes
