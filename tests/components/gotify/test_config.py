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
    pytest.param(camera(), id="camera_empty"),
    pytest.param(
        camera(detection_label="car", send_thumbnail=True, use_public_url=False),
        id="camera_every_key",
    ),
    pytest.param(
        gotify(cameras={"camera_one": None, "camera_two": None}), id="two_cameras"
    ),
    pytest.param(gotify(priority=1), id="priority_min"),
    pytest.param(gotify(priority=10), id="priority_max"),
    pytest.param(gotify(priority="5"), id="priority_string"),
    pytest.param(gotify(priority=5.0), id="priority_whole_float"),
    pytest.param(gotify(detection_label=""), id="detection_label_empty"),
    pytest.param(gotify(image_max_size=0), id="image_max_size_no_resize"),
    pytest.param(gotify(image_max_size=7680), id="image_max_size_max"),
    pytest.param(gotify(image_quality=1), id="image_quality_min"),
    pytest.param(gotify(image_quality=100), id="image_quality_max"),
    pytest.param(camera(detection_label=""), id="camera_detection_label_empty"),
    pytest.param(
        {**gotify(), "logger": {"default_level": "debug"}}, id="other_components"
    ),
    # Rejected by the Voluptuous schema, accepted since the port to Pydantic
    pytest.param(gotify(cameras={}), id="cameras_empty"),
    pytest.param(gotify(send_thumbnail="true"), id="send_thumbnail_string"),
    pytest.param(camera(detection_label=None), id="camera_detection_label_null"),
    pytest.param(camera(send_thumbnail=None), id="camera_send_thumbnail_null"),
    pytest.param(camera(use_public_url=None), id="camera_use_public_url_null"),
]

REJECTED = [
    pytest.param({}, id="gotify_missing"),
    pytest.param({"gotify": None}, id="gotify_null"),
    pytest.param({"gotify": {}}, id="gotify_empty"),
    pytest.param({"gotify": "yes"}, id="gotify_not_a_map"),
    pytest.param(
        {"gotify": {"gotify_token": "t", "cameras": {"camera_one": None}}},
        id="gotify_url_missing",
    ),
    pytest.param(
        {"gotify": {"gotify_url": "u", "cameras": {"camera_one": None}}},
        id="gotify_token_missing",
    ),
    pytest.param(
        {"gotify": {"gotify_url": "u", "gotify_token": "t"}}, id="cameras_missing"
    ),
    pytest.param(gotify(gotify_url=None), id="gotify_url_null"),
    pytest.param(gotify(gotify_url=5), id="gotify_url_number"),
    pytest.param(gotify(gotify_token=12345), id="gotify_token_number"),
    pytest.param(gotify(cameras=None), id="cameras_null"),
    pytest.param(gotify(cameras=["camera_one"]), id="cameras_list"),
    pytest.param(gotify(cameras={"Camera 1": None}), id="camera_identifier_not_a_slug"),
    pytest.param(gotify(cameras={"camera_one": "on"}), id="camera_not_a_map"),
    pytest.param(gotify(priority=0), id="priority_below_range"),
    pytest.param(gotify(priority=11), id="priority_above_range"),
    pytest.param(gotify(priority="high"), id="priority_not_a_number"),
    pytest.param(gotify(priority=None), id="priority_null"),
    pytest.param(gotify(detection_label=5), id="detection_label_number"),
    pytest.param(gotify(detection_label=None), id="detection_label_null"),
    pytest.param(gotify(detection_label=["person", "cat"]), id="detection_label_list"),
    pytest.param(gotify(send_thumbnail="maybe"), id="send_thumbnail_not_a_boolean"),
    pytest.param(gotify(send_thumbnail=None), id="send_thumbnail_null"),
    pytest.param(gotify(use_public_url="maybe"), id="use_public_url_not_a_boolean"),
    pytest.param(gotify(image_max_size=-1), id="image_max_size_negative"),
    pytest.param(gotify(image_max_size=7681), id="image_max_size_above_range"),
    pytest.param(gotify(image_quality=0), id="image_quality_below_range"),
    pytest.param(gotify(image_quality=101), id="image_quality_above_range"),
    pytest.param(camera(detection_label=5), id="camera_detection_label_number"),
    pytest.param(
        camera(send_thumbnail="maybe"), id="camera_send_thumbnail_not_a_boolean"
    ),
    pytest.param(
        camera(use_public_url="maybe"), id="camera_use_public_url_not_a_boolean"
    ),
    # Accepted by the Voluptuous schema, rejected since the port to Pydantic
    pytest.param(gotify(foo=1), id="unknown_key"),
    pytest.param(camera(foo=1), id="unknown_key_in_camera"),
    pytest.param(gotify(priority=5.7), id="priority_fraction"),
    pytest.param(gotify(image_max_size=800.5), id="image_max_size_fraction"),
    pytest.param(gotify(image_quality=90.5), id="image_quality_fraction"),
    pytest.param(gotify(cameras={"": None}), id="camera_identifier_empty"),
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


def test_conversions() -> None:
    """Numbers and booleans written as strings, and whole floats, are converted."""
    validated = validate_config(
        CONFIG_SCHEMA,
        gotify(
            priority="7",
            image_max_size=1920.0,
            send_thumbnail="yes",
            cameras={"camera_one": {"use_public_url": "off"}},
        ),
    )
    assert validated.gotify.priority == 7
    assert validated.gotify.image_max_size == 1920
    assert validated.gotify.send_thumbnail is True
    assert validated.gotify.cameras["camera_one"].use_public_url is False


def test_token_is_secret() -> None:
    """The token is only revealed by get_secret_value, not by repr or a dump."""
    validated = validate_config(CONFIG_SCHEMA, gotify())
    assert validated.gotify.gotify_token.get_secret_value() == "AbCdEf123"
    assert "AbCdEf123" not in repr(validated)
    assert "AbCdEf123" not in str(validated.model_dump())
    assert "AbCdEf123" not in validated.model_dump_json()
