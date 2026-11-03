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
]

REJECTED = [
    pytest.param({"logger": {"default_level": "loud"}}, id="unknown_default_level"),
    pytest.param({"logger": {"logs": {"viseron": "loud"}}}, id="unknown_level_in_logs"),
    pytest.param(
        {"logger": {"cameras": {"camera_one": "loud"}}}, id="unknown_level_in_cameras"
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
    ],
)
def test_validated_config(config: dict[str, Any], expected: dict[str, Any]) -> None:
    """The validated config has defaults filled in and levels in lowercase."""
    validated = validate_config(CONFIG_SCHEMA, {"logger": config})
    assert validated.logger.model_dump() == expected
