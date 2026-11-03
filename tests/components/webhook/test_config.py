"""Tests for the config of the webhook component."""

from __future__ import annotations

from typing import Any

import pytest

from viseron.components.webhook import CONFIG_SCHEMA
from viseron.helpers.config_validation import ConfigValidationError, validate_config

REQUIRED = {"trigger": {"event": "camera_one/motion_detected"}, "url": "http://x"}


def hook(**keys: Any) -> dict[str, Any]:
    """Return a config with one hook that has the required keys and the given ones."""
    return {"webhook": {"cool_hook": {**REQUIRED, **keys}}}


ACCEPTED = [
    pytest.param(hook(), id="minimal"),
    pytest.param(
        {
            "webhook": {
                "cool_hook": {
                    "trigger": {
                        "event": "camera_one/motion_detected",
                        "condition": "{{ event.motion_detected }}\n",
                    },
                    "url": "http://example.com/webhook",
                    "payload": "Motion detected on {{ event.camera_identifier }}!",
                }
            }
        },
        id="docs_example",
    ),
    pytest.param(
        hook(
            trigger={"event": "camera_one/motion_detected", "condition": "{{ 1 }}"},
            url="http://example.com/{{ event.camera_identifier }}",
            method="post",
            headers={"Authorization": "Bearer abc", "X-Camera": "{{ event.name }}"},
            username="user",
            password="pass",
            payload='{"name": "{{ event.name }}"}',
            timeout=5,
            content_type="text/plain",
            verify_ssl=False,
            ca_cert="/config/ca.pem",
        ),
        id="every_key",
    ),
    pytest.param(hook(url=None), id="url_null"),
]

REJECTED = [
    pytest.param(hook(method="head"), id="method_not_supported"),
    pytest.param(hook(username="user"), id="username_without_password"),
    pytest.param(hook(password="pass"), id="password_without_username"),
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


def test_defaults() -> None:
    """Keys that are not set get their defaults."""
    validated = validate_config(CONFIG_SCHEMA, hook())
    assert validated.webhook["cool_hook"].model_dump() == {
        "trigger": {"event": "camera_one/motion_detected", "condition": None},
        "url": "http://x",
        "method": "get",
        "headers": {},
        "username": None,
        "password": None,
        "payload": None,
        "timeout": 10,
        "content_type": "application/json",
        "verify_ssl": True,
        "ca_cert": None,
    }


def test_method_is_lowercased() -> None:
    """The method is accepted in any case and stored in lower case."""
    validated = validate_config(CONFIG_SCHEMA, hook(method="POST"))
    assert validated.webhook["cool_hook"].method == "post"


def test_authentication_error_message() -> None:
    """Setting only one of username and password tells that both are needed."""
    with pytest.raises(
        ConfigValidationError,
        match="webhook.cool_hook: username and password must be provided together",
    ):
        validate_config(CONFIG_SCHEMA, hook(username="user"))
