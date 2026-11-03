"""Tests for the config of the discord component."""

from __future__ import annotations

from typing import Any

import pytest

from viseron.components.discord import CONFIG_SCHEMA
from viseron.helpers.config_validation import validate_config

REQUIRED = {
    "webhook_url": "https://discord.com/api/webhooks/123/AbCdEf",
    "cameras": {"camera_one": None},
}


def discord(**keys: Any) -> dict[str, Any]:
    """Return a config with the required discord keys and the given ones."""
    return {"discord": {**REQUIRED, **keys}}


def camera(**keys: Any) -> dict[str, Any]:
    """Return a discord config where camera_one has the given keys."""
    return discord(cameras={"camera_one": keys})


ACCEPTED = [
    pytest.param(discord(), id="minimal"),
    pytest.param(
        {
            "discord": {
                "webhook_url": "https://discord.com/api/webhooks/your-webhook-url",
                "send_detection_thumbnail": True,
                "send_detection_video": True,
                "max_video_size_mb": 8,
                "detection_label": "person",
                "cameras": {
                    "camera_1": {
                        "webhook_url": (
                            "https://discord.com/api/webhooks/camera1-specific-webhook"
                        ),
                        "send_detection_thumbnail": False,
                        "send_detection_video": False,
                        "max_video_size_mb": 50,
                        "detection_label": "car",
                    },
                    "camera_2": {
                        "webhook_url": (
                            "https://discord.com/api/webhooks/camera2-specific-webhook"
                        ),
                    },
                },
            }
        },
        id="docs_example",
    ),
    pytest.param(
        discord(
            detection_labels=["person", "car"],
            send_detection_thumbnail=False,
            send_detection_video=False,
            max_video_size_mb=50,
        ),
        id="every_key",
    ),
    pytest.param(
        camera(
            webhook_url="https://discord.com/api/webhooks/456/GhIjKl",
            detection_label="car",
            detection_labels=["car", "truck"],
            send_detection_thumbnail=False,
            send_detection_video=False,
            max_video_size_mb=50,
        ),
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
        pytest.param(discord(detection_label="person"), id="global"),
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
    validated = validate_config(CONFIG_SCHEMA, discord())
    assert validated.discord.model_dump(exclude={"webhook_url"}) == {
        "detection_label": None,
        "detection_labels": ["person"],
        "send_detection_thumbnail": True,
        "send_detection_video": True,
        "max_video_size_mb": 8,
        "cameras": {
            "camera_one": {
                "webhook_url": None,
                "detection_label": None,
                "detection_labels": None,
                "send_detection_thumbnail": None,
                "send_detection_video": None,
                "max_video_size_mb": None,
            }
        },
    }
