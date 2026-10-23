"""Tests for the config of the discord component."""

from __future__ import annotations

from typing import Any

import pytest

from viseron.components.discord import CONFIG_SCHEMA
from viseron.helpers.config_validation import ConfigValidationError, validate_config

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
    pytest.param(camera(), id="camera_empty"),
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
    pytest.param(
        discord(cameras={"camera_one": None, "camera_two": None}), id="two_cameras"
    ),
    pytest.param(discord(detection_label=""), id="detection_label_empty"),
    pytest.param(discord(detection_labels=[]), id="detection_labels_empty"),
    pytest.param(discord(max_video_size_mb=0), id="max_video_size_mb_zero"),
    pytest.param(discord(max_video_size_mb=-1), id="max_video_size_mb_negative"),
    pytest.param(discord(max_video_size_mb=True), id="max_video_size_mb_boolean"),
    pytest.param(camera(detection_label=""), id="camera_detection_label_empty"),
    pytest.param(camera(detection_labels=None), id="camera_detection_labels_null"),
    pytest.param(camera(detection_labels=[]), id="camera_detection_labels_empty"),
    pytest.param(
        {**discord(), "logger": {"default_level": "debug"}}, id="other_components"
    ),
    # Rejected by the Voluptuous schema, accepted since the port to Pydantic
    pytest.param(discord(cameras={}), id="cameras_empty"),
    pytest.param(discord(max_video_size_mb="8"), id="max_video_size_mb_string"),
    pytest.param(discord(max_video_size_mb=8.0), id="max_video_size_mb_whole_float"),
    pytest.param(
        discord(send_detection_thumbnail="true"), id="send_detection_thumbnail_string"
    ),
    pytest.param(discord(send_detection_video=1), id="send_detection_video_number"),
    pytest.param(discord(detection_label=None), id="detection_label_null"),
    pytest.param(camera(webhook_url=None), id="camera_webhook_url_null"),
    pytest.param(camera(detection_label=None), id="camera_detection_label_null"),
    pytest.param(
        camera(send_detection_thumbnail=None), id="camera_send_detection_thumbnail_null"
    ),
    pytest.param(
        camera(send_detection_thumbnail="true"),
        id="camera_send_detection_thumbnail_string",
    ),
    pytest.param(
        camera(send_detection_video=None), id="camera_send_detection_video_null"
    ),
    pytest.param(camera(max_video_size_mb=None), id="camera_max_video_size_mb_null"),
    pytest.param(camera(max_video_size_mb="8"), id="camera_max_video_size_mb_string"),
]

REJECTED = [
    pytest.param({}, id="discord_missing"),
    pytest.param({"discord": None}, id="discord_null"),
    pytest.param({"discord": {}}, id="discord_empty"),
    pytest.param({"discord": "yes"}, id="discord_not_a_map"),
    pytest.param(
        {"discord": {"cameras": {"camera_one": None}}}, id="webhook_url_missing"
    ),
    pytest.param({"discord": {"webhook_url": "u"}}, id="cameras_missing"),
    pytest.param(discord(webhook_url=None), id="webhook_url_null"),
    pytest.param(discord(webhook_url=5), id="webhook_url_number"),
    pytest.param(discord(detection_label=5), id="detection_label_number"),
    pytest.param(discord(detection_labels=None), id="detection_labels_null"),
    pytest.param(discord(detection_labels="person"), id="detection_labels_string"),
    pytest.param(discord(detection_labels=[5]), id="detection_labels_number"),
    pytest.param(
        discord(send_detection_thumbnail="maybe"),
        id="send_detection_thumbnail_not_a_boolean",
    ),
    pytest.param(
        discord(send_detection_thumbnail=None), id="send_detection_thumbnail_null"
    ),
    pytest.param(
        discord(send_detection_video="maybe"), id="send_detection_video_not_a_boolean"
    ),
    pytest.param(discord(send_detection_video=None), id="send_detection_video_null"),
    pytest.param(discord(max_video_size_mb=8.5), id="max_video_size_mb_fraction"),
    pytest.param(discord(max_video_size_mb="big"), id="max_video_size_mb_not_a_number"),
    pytest.param(discord(max_video_size_mb=None), id="max_video_size_mb_null"),
    pytest.param(discord(cameras=None), id="cameras_null"),
    pytest.param(discord(cameras=["camera_one"]), id="cameras_list"),
    pytest.param(
        discord(cameras={"Camera 1": None}), id="camera_identifier_not_a_slug"
    ),
    pytest.param(discord(cameras={"camera_one": "on"}), id="camera_not_a_map"),
    pytest.param(camera(webhook_url=5), id="camera_webhook_url_number"),
    pytest.param(camera(detection_label=5), id="camera_detection_label_number"),
    pytest.param(camera(detection_labels="car"), id="camera_detection_labels_string"),
    pytest.param(
        camera(send_detection_thumbnail="maybe"),
        id="camera_send_detection_thumbnail_not_a_boolean",
    ),
    pytest.param(
        camera(send_detection_video="maybe"),
        id="camera_send_detection_video_not_a_boolean",
    ),
    pytest.param(camera(max_video_size_mb=8.5), id="camera_max_video_size_mb_fraction"),
    pytest.param(
        camera(max_video_size_mb="big"), id="camera_max_video_size_mb_not_a_number"
    ),
    # Accepted by the Voluptuous schema, rejected since the port to Pydantic
    pytest.param(discord(foo=1), id="unknown_key"),
    pytest.param(camera(foo=1), id="unknown_key_in_camera"),
    pytest.param(discord(cameras={"": None}), id="camera_identifier_empty"),
    pytest.param(
        discord(cameras={"camera_one": None, "Camera 1": None}),
        id="camera_identifier_not_a_slug_next_to_valid",
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


def test_conversions() -> None:
    """Numbers and booleans written as strings, and whole floats, are converted."""
    validated = validate_config(
        CONFIG_SCHEMA,
        discord(
            max_video_size_mb="50",
            send_detection_video="off",
            cameras={
                "camera_one": {"max_video_size_mb": 25.0, "send_detection_thumbnail": 0}
            },
        ),
    )
    assert validated.discord.max_video_size_mb == 50
    assert validated.discord.send_detection_video is False
    assert validated.discord.cameras["camera_one"].max_video_size_mb == 25
    assert validated.discord.cameras["camera_one"].send_detection_thumbnail is False
