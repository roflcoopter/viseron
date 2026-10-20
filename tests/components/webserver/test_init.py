"""Tests for the webserver component."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.components.webserver.common import TestAppBase

if TYPE_CHECKING:
    from viseron.components.webserver.rate_limit import RateLimiter


def _limits(limiter: RateLimiter) -> tuple[int, float]:
    """Return the max attempts and the window of a rate limiter."""
    return limiter._max_attempts, limiter._window_seconds


class TestRateLimitDefaults(TestAppBase):
    """Rate limiters without auth config."""

    config = {"webserver": None}

    def test_rate_limiters(self) -> None:
        """Each bucket gets its default limits."""
        limiters = self.webserver.rate_limiters
        assert _limits(limiters["login"]) == (10, 60)
        assert _limits(limiters["token"]) == (30, 60)
        assert _limits(limiters["onboarding"]) == (5, 60)


class TestRateLimitConfig(TestAppBase):
    """Rate limiters with auth config."""

    config = {
        "webserver": {
            "auth": {
                "rate_limits": {
                    "login": {"max_attempts": 3},
                    "token": {"window_seconds": 30},
                }
            }
        }
    }

    def test_rate_limiters(self) -> None:
        """A configured limit replaces the default of its own key only."""
        limiters = self.webserver.rate_limiters
        assert _limits(limiters["login"]) == (3, 60)
        assert _limits(limiters["token"]) == (30, 30)
        assert _limits(limiters["onboarding"]) == (5, 60)
