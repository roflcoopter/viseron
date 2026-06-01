"""Rate limiter for sensitive auth endpoints.

This is a deliberately simple sliding-window limiter intended
for endpoints that are easy to abuse but rarely hit in normal use.
It does not survive a restart.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    """Sliding-window rate limiter keyed by an arbitrary identifier (e.g. IP).

    max_attempts requests are allowed per window_seconds per key.
    """

    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._last_seen: dict[str, float] = {}
        self._lock = Lock()
        self._eviction_interval = window_seconds * 2
        self._next_eviction: float = 0.0

    def _evict_stale_keys(self, now: float) -> None:
        """Remove keys that have had no activity within the current window."""
        if now < self._next_eviction:
            return
        cutoff = now - self._window_seconds
        stale = [k for k, last in self._last_seen.items() if last <= cutoff]
        for k in stale:
            self._events.pop(k, None)
            self._last_seen.pop(k, None)
        self._next_eviction = now + self._eviction_interval

    def _prune(self, key: str, now: float) -> deque[float]:
        self._evict_stale_keys(now)
        events = self._events[key]
        cutoff = now - self._window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        return events

    def check(self, key: str) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds) and record the attempt.

        retry_after_seconds is 0 when allowed, otherwise the number of
        seconds the caller should wait before the next attempt is allowed.
        """
        now = time.monotonic()
        with self._lock:
            self._last_seen[key] = now
            events = self._prune(key, now)
            if len(events) >= self._max_attempts:
                retry_after = max(0.0, self._window_seconds - (now - events[0]))
                return False, retry_after
            events.append(now)
            return True, 0.0

    def reset(self, key: str) -> None:
        """Forget all recorded events for key.

        Call after a successful authentication so legitimate users are not
        penalised by their own earlier failures.
        """
        with self._lock:
            self._events.pop(key, None)
            self._last_seen.pop(key, None)
