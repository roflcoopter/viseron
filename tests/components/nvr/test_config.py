"""Tests for the NVR component configuration."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from viseron.components.nvr import CONFIG_SCHEMA, optional_domains, setup_domains
from viseron.components.nvr.const import CAMERA, COMPONENT, DOMAIN
from viseron.helpers.config_validation import ConfigValidationError, validate_config


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"nvr": {"front": None}}, id="null_camera_config"),
        pytest.param({"nvr": {"front": {}}}, id="empty_camera_config"),
        pytest.param({"nvr": {"front": {}, "back": None}}, id="multiple_cameras"),
        pytest.param(
            {"nvr": {"front": {}}, "logger": {}}, id="other_component_ignored"
        ),
    ],
)
def test_config_is_accepted(config: dict) -> None:
    """Valid NVR camera mappings pass validation."""
    validate_config(CONFIG_SCHEMA, config)


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({}, id="missing_nvr"),
        pytest.param({"nvr": {}}, id="empty_nvr"),
        pytest.param({"nvr": None}, id="null_nvr"),
        pytest.param({"nvr": []}, id="list_nvr"),
        pytest.param({"nvr": {"Camera 1": {}}}, id="invalid_camera_identifier"),
        pytest.param({"nvr": {"front": {"unexpected": True}}}, id="unknown_option"),
    ],
)
def test_config_is_rejected(config: dict) -> None:
    """Invalid NVR camera mappings are rejected."""
    with pytest.raises(ConfigValidationError):
        validate_config(CONFIG_SCHEMA, config)


def test_null_camera_config_is_normalized() -> None:
    """A null camera section remains compatible with the legacy schema."""
    validated = validate_config(CONFIG_SCHEMA, {"nvr": {"front": None}})
    assert validated.nvr["front"].model_dump() == {}


def test_setup_domains_passes_dictionary_config() -> None:
    """Downstream NVR setup receives the same dictionary boundary as before."""
    vis = Mock()
    config = validate_config(CONFIG_SCHEMA, {"nvr": {"front": None, "back": {}}})

    with patch("viseron.components.nvr.setup_domain") as setup_domain:
        setup_domains(vis, config)

    assert setup_domain.call_count == 2
    for call, identifier in zip(
        setup_domain.call_args_list, ("front", "back"), strict=True
    ):
        args, kwargs = call
        assert args == (vis, COMPONENT, DOMAIN, {"front": {}, "back": {}})
        assert kwargs["identifier"] == identifier
        assert kwargs["require_domains"][0].domain == CAMERA
        assert kwargs["require_domains"][0].identifier == identifier
        assert kwargs["optional_domains"] == optional_domains(identifier)
