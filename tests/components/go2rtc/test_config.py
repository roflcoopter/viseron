"""Tests for go2rtc configuration compatibility."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol
from ruamel.yaml import YAML

from viseron.components.go2rtc import CONFIG_SCHEMA, setup
from viseron.helpers.config_validation import ConfigValidationError, validate_config


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"streams": {"front": ["rtsp://camera/live"]}, "api": {"listen": ":1984"}},
        {"custom": [None, True, 42, {"nested": "value"}], 1: "key"},
    ],
)
def test_passthrough(options: dict[Any, Any]) -> None:
    """Preserve arbitrary go2rtc options and ignore other components."""
    config = {"go2rtc": options, "logger": {}}
    legacy = vol.Schema(
        {vol.Required("go2rtc"): vol.Schema({}, extra=vol.ALLOW_EXTRA)},
        extra=vol.ALLOW_EXTRA,
    )
    validated = validate_config(CONFIG_SCHEMA, config)
    assert validated.go2rtc == legacy(config)["go2rtc"]


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"go2rtc": None},
        {"go2rtc": []},
        {"go2rtc": "streams"},
        {"go2rtc": 1},
        {"go2rtc": True},
    ],
)
def test_invalid_config(config: dict[str, Any]) -> None:
    """Require a mapping rather than coercing invalid component sections."""
    with pytest.raises(ConfigValidationError):
        validate_config(CONFIG_SCHEMA, config)


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"streams": {"front": ["rtsp://camera/live"]}, "custom": {"enabled": True}},
        {"streams": {"front": "rtsp://camera/live"}, "custom": [None, 42, False]},
    ],
)
def test_setup_writes_yaml(tmp_path: Path, options: dict[str, Any]) -> None:
    """Keep YAML output and the dictionary read by ONVIF compatible."""
    target = tmp_path / "go2rtc.yaml"
    vis = Mock(data={})
    with (
        patch("viseron.components.go2rtc.GO2RTC_CONFIG", str(target)),
        patch("viseron.components.go2rtc.Go2RTC.restart") as restart,
    ):
        assert setup(vis, validate_config(CONFIG_SCHEMA, {"go2rtc": options}))
    assert YAML().load(target) == options
    assert vis.data["go2rtc"]._config["go2rtc"] == options
    restart.assert_called_once_with()
