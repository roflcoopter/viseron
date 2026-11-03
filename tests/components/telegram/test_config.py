"""Tests for the config of the telegram component."""

from __future__ import annotations

from typing import Any

import pytest

from viseron.components.telegram import CONFIG_SCHEMA
from viseron.helpers.config_validation import validate_config

REQUIRED = {
    "telegram_bot_token": "123456:AbCdEf",
    "telegram_chat_ids": [123456789],
    "cameras": {"camera_one": None},
}


def telegram(**keys: Any) -> dict[str, Any]:
    """Return a config with the required telegram keys and the given ones."""
    return {"telegram": {**REQUIRED, **keys}}


def camera(**keys: Any) -> dict[str, Any]:
    """Return a telegram config where camera_one has the given keys."""
    return telegram(cameras={"camera_one": keys})


ACCEPTED = [
    pytest.param(telegram(), id="minimal"),
    pytest.param(
        {
            "telegram": {
                "telegram_bot_token": "123456:AbCdEf",
                "telegram_chat_ids": [123456789],
                "detection_label": "person",
                "send_detection_thumbnail": True,
                "send_detection_video": True,
                "send_detection_message": False,
                "cameras": {"camera_1": None, "camera_2": None},
            }
        },
        id="docs_example",
    ),
    pytest.param(
        telegram(
            telegram_user_ids=[1, 2],
            detection_labels=["person", "car"],
            send_detection_thumbnail=True,
            send_detection_video=True,
            send_detection_message=False,
            telegram_log_ids=True,
        ),
        id="every_key",
    ),
    pytest.param(
        camera(detection_label="car", detection_labels=["car", "truck"]),
        id="camera_every_key",
    ),
]


@pytest.mark.parametrize("config", ACCEPTED)
def test_config_is_accepted(config: dict) -> None:
    """A valid config passes validation."""
    validate_config(CONFIG_SCHEMA, config)


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(telegram(detection_label="person"), id="global"),
        pytest.param(camera(detection_label="person"), id="camera"),
    ],
)
def test_deprecated_detection_label_is_logged(
    config: dict, caplog: pytest.LogCaptureFixture
) -> None:
    """Setting detection_label logs that it is deprecated."""
    validate_config(CONFIG_SCHEMA, config)
    assert "Config option 'detection_label' is deprecated" in caplog.text


def test_defaults() -> None:
    """Keys that are not set get their defaults, camera keys are unset."""
    validated = validate_config(CONFIG_SCHEMA, telegram())
    assert validated.telegram.model_dump(exclude={"telegram_bot_token"}) == {
        "telegram_chat_ids": [123456789],
        "telegram_user_ids": [],
        "detection_label": None,
        "detection_labels": ["person"],
        "send_detection_thumbnail": False,
        "send_detection_video": False,
        "send_detection_message": True,
        "telegram_log_ids": False,
        "cameras": {"camera_one": {"detection_label": None, "detection_labels": None}},
    }
