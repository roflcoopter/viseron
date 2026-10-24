"""Tests for the config of the webserver component."""

from __future__ import annotations

from typing import Any

import pytest

from viseron.components.webserver import CONFIG_SCHEMA
from viseron.helpers.config_validation import ConfigValidationError, validate_config

EVERY_KEY = {
    "webserver": {
        "port": 8888,
        "debug": True,
        "subpath": "/viseron",
        "public_base_url": "https://viseron.example.com",
        "public_url_expiry_hours": 240,
        "public_url_max_downloads": 3,
        "auth": {
            "session_expiry": {"days": 1, "hours": 2, "minutes": 3},
            "rate_limits": {
                "login": {"max_attempts": 5, "window_seconds": 30},
                "token": {"max_attempts": 50, "window_seconds": 120.5},
                "onboarding": {"max_attempts": 2, "window_seconds": 600},
            },
        },
    }
}

ACCEPTED = [
    pytest.param(EVERY_KEY, id="every_key"),
    pytest.param(
        {
            "webserver": {
                "port": 8888,
                "public_base_url": "https://public.dns-viseron.org",
                "public_url_expiry_hours": 240,
                "public_url_max_downloads": 3,
            }
        },
        id="docs_example",
    ),
    pytest.param({"webserver": {"subpath": "/viseron"}}, id="docs_subpath_example"),
    pytest.param({"webserver": {"auth": None}}, id="docs_auth_example"),
    pytest.param({"webserver": {"port": 1024}}, id="port_min"),
    pytest.param({"webserver": {"port": 49151}}, id="port_max"),
    pytest.param({"webserver": {"public_url_expiry_hours": 1}}, id="expiry_hours_min"),
    pytest.param(
        {"webserver": {"public_url_expiry_hours": 744}}, id="expiry_hours_max"
    ),
    pytest.param(
        {"webserver": {"public_url_max_downloads": 0}}, id="max_downloads_unlimited"
    ),
]

REJECTED = [
    pytest.param({"webserver": {"port": 80}}, id="port_below_range"),
    pytest.param({"webserver": {"port": 49152}}, id="port_above_range"),
    pytest.param(
        {"webserver": {"public_url_expiry_hours": 0}}, id="expiry_hours_below_range"
    ),
    pytest.param(
        {"webserver": {"public_url_expiry_hours": 745}}, id="expiry_hours_above_range"
    ),
    pytest.param(
        {"webserver": {"public_url_max_downloads": -1}}, id="max_downloads_negative"
    ),
    pytest.param(
        {"webserver": {"auth": {"session_expiry": {"days": -1}}}},
        id="session_expiry_negative",
    ),
    pytest.param(
        {"webserver": {"auth": {"rate_limits": {"login": {"max_attempts": 0}}}}},
        id="max_attempts_zero",
    ),
    pytest.param(
        {"webserver": {"auth": {"rate_limits": {"login": {"window_seconds": 0.5}}}}},
        id="window_seconds_below_range",
    ),
]


@pytest.mark.parametrize("config", ACCEPTED)
def test_config_is_accepted(config: dict) -> None:
    """A valid config passes validation."""
    validate_config(CONFIG_SCHEMA, config)


@pytest.mark.parametrize("config", REJECTED)
def test_config_is_rejected(config: dict) -> None:
    """A config that is not valid fails validation."""
    with pytest.raises(ConfigValidationError):
        validate_config(CONFIG_SCHEMA, config)


DEFAULT_RATE_LIMITS = {
    "login": {"max_attempts": 10, "window_seconds": 60.0},
    "token": {"max_attempts": 30, "window_seconds": 60.0},
    "onboarding": {"max_attempts": 5, "window_seconds": 60.0},
}


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({}, id="webserver_missing"),
        pytest.param({"webserver": None}, id="webserver_null"),
    ],
)
def test_defaults(config: dict[str, Any]) -> None:
    """A webserver without config has auth disabled and the defaults filled in."""
    validated = validate_config(CONFIG_SCHEMA, config)
    assert validated.webserver.model_dump() == {
        "port": None,
        "debug": False,
        "subpath": None,
        "public_base_url": None,
        "public_url_expiry_hours": 24,
        "public_url_max_downloads": 0,
        "auth": None,
    }


@pytest.mark.parametrize(
    "auth",
    [pytest.param(None, id="null"), pytest.param({}, id="empty")],
)
def test_auth_key_enables_auth(auth: dict[str, Any] | None) -> None:
    """Writing the auth key, even without a value, enables auth with defaults."""
    validated = validate_config(CONFIG_SCHEMA, {"webserver": {"auth": auth}})
    assert validated.webserver.auth.model_dump() == {
        "session_expiry": None,
        "rate_limits": DEFAULT_RATE_LIMITS,
    }


def test_rate_limit_keeps_defaults_of_its_bucket() -> None:
    """A rate limit that sets one key keeps the defaults of its own bucket."""
    validated = validate_config(
        CONFIG_SCHEMA,
        {
            "webserver": {
                "auth": {
                    "rate_limits": {
                        "login": {"max_attempts": 3},
                        "token": {"window_seconds": 30},
                        "onboarding": None,
                    }
                }
            }
        },
    )
    assert validated.webserver.auth.rate_limits.model_dump() == {
        "login": {"max_attempts": 3, "window_seconds": 60.0},
        "token": {"max_attempts": 30, "window_seconds": 30.0},
        "onboarding": {"max_attempts": 5, "window_seconds": 60.0},
    }


@pytest.mark.parametrize(
    ("session_expiry", "expected"),
    [
        pytest.param(None, None, id="null"),
        pytest.param({}, {"days": 0, "hours": 0, "minutes": 0}, id="empty"),
        pytest.param({"hours": 1}, {"days": 0, "hours": 1, "minutes": 0}, id="one_key"),
    ],
)
def test_session_expiry(
    session_expiry: dict[str, Any] | None, expected: dict[str, Any] | None
) -> None:
    """Keys left out of session_expiry are zero."""
    validated = validate_config(
        CONFIG_SCHEMA, {"webserver": {"auth": {"session_expiry": session_expiry}}}
    )
    dumped = validated.webserver.auth.model_dump()
    assert dumped["session_expiry"] == expected
