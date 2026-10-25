"""Tests for the config of the gotify component."""

from __future__ import annotations

from typing import Any

import pytest

from viseron.components.gotify import CONFIG_SCHEMA
from viseron.helpers.config_validation import ConfigValidationError, validate_config

REQUIRED = {
    "gotify_url": "https://gotify.example.com",
    "gotify_token": "AbCdEf123",
    "cameras": {"camera_one": None},
}


def gotify(**keys: Any) -> dict[str, Any]:
    """Return a config with the required gotify keys and the given ones."""
    return {"gotify": {**REQUIRED, **keys}}


def camera(**keys: Any) -> dict[str, Any]:
    """Return a gotify config where camera_one has the given keys."""
    return gotify(cameras={"camera_one": keys})


ACCEPTED = [
    pytest.param(gotify(), id="minimal"),
    pytest.param(
        {
            "gotify": {
                "gotify_url": "https://gotify.example.com",
                "gotify_token": "YOUR_APPLICATION_TOKEN",
                "priority": 5,
                "detection_label": "person,cat",
                "send_thumbnail": True,
                "use_public_url": True,
                "image_max_size": 800,
                "image_quality": 95,
                "cameras": {
                    "camera1": None,
                    "camera2": {
                        "detection_label": "car,truck",
                        "send_thumbnail": False,
                    },
                },
            }
        },
        id="docs_example",
    ),
    pytest.param(
        camera(detection_label="car", send_thumbnail=True, use_public_url=False),
        id="camera_every_key",
    ),
    pytest.param(gotify(priority=1), id="priority_min"),
    pytest.param(gotify(priority=10), id="priority_max"),
    pytest.param(gotify(image_max_size=0), id="image_max_size_no_resize"),
    pytest.param(gotify(image_max_size=7680), id="image_max_size_max"),
    pytest.param(gotify(image_quality=1), id="image_quality_min"),
    pytest.param(gotify(image_quality=100), id="image_quality_max"),
]

REJECTED = [
    pytest.param(gotify(priority=0), id="priority_below_range"),
    pytest.param(gotify(priority=11), id="priority_above_range"),
    pytest.param(gotify(image_max_size=-1), id="image_max_size_negative"),
    pytest.param(gotify(image_max_size=7681), id="image_max_size_above_range"),
    pytest.param(gotify(image_quality=0), id="image_quality_below_range"),
    pytest.param(gotify(image_quality=101), id="image_quality_above_range"),
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
    """Keys that are not set get their defaults, camera overrides are unset."""
    validated = validate_config(CONFIG_SCHEMA, gotify())
    assert validated.gotify.model_dump(exclude={"gotify_token"}) == {
        "gotify_url": "https://gotify.example.com",
        "priority": 5,
        "detection_label": "person",
        "send_thumbnail": False,
        "use_public_url": False,
        "image_max_size": 800,
        "image_quality": 95,
        "cameras": {
            "camera_one": {
                "detection_label": None,
                "send_thumbnail": None,
                "use_public_url": None,
            }
        },
    }
