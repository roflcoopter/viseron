"""Tests for the config of the logger component."""

from __future__ import annotations

from typing import Any

import pytest

from viseron.components.logger import CONFIG_SCHEMA
from viseron.helpers.config_validation import ConfigValidationError, validate_config

ACCEPTED = [
    pytest.param({"logger": {}}, id="minimal"),
    pytest.param(
        {
            "logger": {
                "default_level": "info",
                "logs": {
                    "viseron.components.ffmpeg": "debug",
                    "viseron.components.edgetpu": "debug",
                },
                "cameras": {"camera_one": "debug"},
            }
        },
        id="every_key",
    ),
    pytest.param({"logger": {"cameras": {"camera_one": "debug"}}}, id="only_cameras"),
    pytest.param(
        {"logger": {"logs": {"viseron.components.ffmpeg": "debug"}}}, id="only_logs"
    ),
    pytest.param({"logger": {"default_level": "debug"}}, id="only_default_level"),
    pytest.param(
        {
            "logger": {
                "default_level": "DEBUG",
                "logs": {"viseron": "Info"},
                "cameras": {"camera_one": "WARNING"},
            }
        },
        id="levels_in_any_case",
    ),
    pytest.param({"logger": {"cameras": None}}, id="cameras_null"),
    pytest.param({"logger": {"cameras": {}}}, id="cameras_empty"),
    pytest.param({"logger": {"logs": None}}, id="logs_null"),
    pytest.param({"logger": {"logs": {}}}, id="logs_empty"),
    pytest.param(
        {"logger": {}, "mqtt": {"broker": "localhost"}}, id="other_components"
    ),
]

REJECTED = [
    pytest.param({}, id="logger_missing"),
    pytest.param({"logger": None}, id="logger_null"),
    pytest.param({"logger": {"level": "info"}}, id="unknown_key"),
    pytest.param({"logger": {"default_level": "loud"}}, id="unknown_default_level"),
    pytest.param({"logger": {"default_level": 5}}, id="default_level_number"),
    pytest.param({"logger": {"default_level": True}}, id="default_level_boolean"),
    pytest.param({"logger": {"default_level": None}}, id="default_level_null"),
    pytest.param({"logger": {"logs": "info"}}, id="logs_not_a_map"),
    pytest.param({"logger": {"logs": {"viseron": "loud"}}}, id="unknown_level_in_logs"),
    pytest.param({"logger": {"logs": {5: "info"}}}, id="logger_name_not_a_string"),
    pytest.param({"logger": {"cameras": "info"}}, id="cameras_not_a_map"),
    pytest.param(
        {"logger": {"cameras": {"camera_one": "loud"}}}, id="unknown_level_in_cameras"
    ),
    pytest.param(
        {"logger": {"cameras": {"Camera One": "info"}}}, id="invalid_camera_identifier"
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
    ("config", "expected"),
    [
        pytest.param(
            {},
            {"default_level": "info", "logs": {}, "cameras": {}},
            id="defaults",
        ),
        pytest.param(
            {
                "default_level": "DEBUG",
                "logs": {"viseron": "Info"},
                "cameras": {"camera_one": "WARNING"},
            },
            {
                "default_level": "debug",
                "logs": {"viseron": "info"},
                "cameras": {"camera_one": "warning"},
            },
            id="levels_are_lowercased",
        ),
        pytest.param(
            {"logs": None, "cameras": None},
            {"default_level": "info", "logs": {}, "cameras": {}},
            id="null_map_is_empty",
        ),
    ],
)
def test_validated_config(config: dict[str, Any], expected: dict[str, Any]) -> None:
    """The validated config has defaults filled in and levels in lowercase."""
    validated = validate_config(CONFIG_SCHEMA, {"logger": config})
    assert validated.logger.model_dump() == expected
