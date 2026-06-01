"""Tests for the in-memory auth rate limiter."""

from __future__ import annotations

import pytest

from viseron.components.webserver.rate_limit import RateLimiter


class TestRateLimiterConstruction:
    """Construction-time validation."""

    @pytest.mark.parametrize("max_attempts", [0, -1, -100])
    def test_invalid_max_attempts(self, max_attempts: int) -> None:
        """max_attempts must be positive."""
        with pytest.raises(ValueError, match="max_attempts"):
            RateLimiter(max_attempts, 60)

    @pytest.mark.parametrize("window", [0, -1, -0.5])
    def test_invalid_window(self, window: float) -> None:
        """window_seconds must be positive."""
        with pytest.raises(ValueError, match="window_seconds"):
            RateLimiter(5, window)


class TestRateLimiterCheck:
    """Sliding-window behaviour of ``check``."""

    def test_allows_up_to_max_attempts(self) -> None:
        """The first ``max_attempts`` calls are allowed."""
        limiter = RateLimiter(3, 60)
        for _ in range(3):
            allowed, retry_after = limiter.check("ip")
            assert allowed is True
            assert retry_after == 0.0

    def test_blocks_after_max_attempts(self) -> None:
        """Once the budget is spent, further calls are denied."""
        limiter = RateLimiter(2, 60)
        limiter.check("ip")
        limiter.check("ip")
        allowed, retry_after = limiter.check("ip")
        assert allowed is False
        assert retry_after > 0.0
        assert retry_after <= 60.0

    def test_keys_are_independent(self) -> None:
        """Throttling one key must not affect another."""
        limiter = RateLimiter(1, 60)
        assert limiter.check("a") == (True, 0.0)
        assert limiter.check("a")[0] is False
        # A different key still has its full budget.
        assert limiter.check("b") == (True, 0.0)

    def test_window_expiry_releases_budget(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Events older than the window are pruned and budget is restored."""
        current = [1000.0]

        def fake_monotonic() -> float:
            return current[0]

        monkeypatch.setattr(
            "viseron.components.webserver.rate_limit.time.monotonic",
            fake_monotonic,
        )

        limiter = RateLimiter(2, 10)
        assert limiter.check("ip")[0] is True
        assert limiter.check("ip")[0] is True
        assert limiter.check("ip")[0] is False

        # Advance past the window and the oldest event should age out.
        current[0] += 11
        assert limiter.check("ip")[0] is True

    def test_retry_after_decreases_over_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``retry_after`` reflects how long until the oldest event expires."""
        current = [1000.0]

        def fake_monotonic() -> float:
            return current[0]

        monkeypatch.setattr(
            "viseron.components.webserver.rate_limit.time.monotonic",
            fake_monotonic,
        )

        limiter = RateLimiter(1, 10)
        limiter.check("ip")  # records at t=1000
        _, first_retry = limiter.check("ip")
        current[0] += 4
        _, later_retry = limiter.check("ip")
        assert later_retry < first_retry
        assert later_retry == pytest.approx(6.0, abs=0.01)

    def test_stale_keys_are_evicted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Inactive keys are removed once eviction is due."""
        current = [1000.0]

        def fake_monotonic() -> float:
            return current[0]

        monkeypatch.setattr(
            "viseron.components.webserver.rate_limit.time.monotonic",
            fake_monotonic,
        )

        limiter = RateLimiter(1, 10)
        assert limiter.check("stale") == (True, 0.0)

        current[0] += 15
        assert limiter.check("recent") == (True, 0.0)

        current[0] += 6
        assert limiter.check("trigger") == (True, 0.0)

        assert "stale" not in limiter._events
        assert "stale" not in limiter._last_seen
        assert "recent" in limiter._events
        assert "recent" in limiter._last_seen


class TestRateLimiterReset:
    """``reset`` clears recorded events for a single key."""

    def test_reset_restores_full_budget(self) -> None:
        """After reset, the key is allowed up to ``max_attempts`` again."""
        limiter = RateLimiter(2, 60)
        limiter.check("ip")
        limiter.check("ip")
        assert limiter.check("ip")[0] is False

        limiter.reset("ip")

        assert "ip" not in limiter._last_seen

        assert limiter.check("ip")[0] is True
        assert limiter.check("ip")[0] is True
        assert limiter.check("ip")[0] is False

    def test_reset_only_affects_target_key(self) -> None:
        """Resetting one key must not unblock another."""
        limiter = RateLimiter(1, 60)
        limiter.check("a")
        limiter.check("b")
        assert limiter.check("a")[0] is False
        assert limiter.check("b")[0] is False

        limiter.reset("a")

        assert limiter.check("a")[0] is True
        assert limiter.check("b")[0] is False

    def test_reset_unknown_key_is_noop(self) -> None:
        """Resetting a key that was never seen does not raise."""
        limiter = RateLimiter(1, 60)
        limiter.reset("never-seen")  # must not raise
        assert limiter.check("never-seen")[0] is True
