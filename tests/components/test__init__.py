"""Test component module."""
from unittest.mock import Mock, patch

import pytest

from viseron.components import (
    CORE_COMPONENTS,
    LOGGING_COMPONENTS,
    Component,
    setup_components,
)
from viseron.const import FAILED, LOADED, LOADING

CONFIG = {"logger": {"default_level": "debug"}}
BAD_CONFIG = {"logger": {"bad_option": "debug"}}
MISSING_CONFIG = {"logger": {"default_level": "debug"}, "bad_component": {}}


@pytest.mark.parametrize(
    "config, loaded, loading, failed, caplog_text",
    [
        (CONFIG, set(LOGGING_COMPONENTS) | set(CORE_COMPONENTS), set(), set(), None),
        (
            BAD_CONFIG,
            set(CORE_COMPONENTS),
            set(),
            {"logger"},
            (
                "Error setting up component logger: "
                "extra keys not allowed @ data['logger']['bad_option']"
            ),
        ),
        (
            MISSING_CONFIG,
            set(LOGGING_COMPONENTS) | set(CORE_COMPONENTS),
            set(),
            {"bad_component"},
            (
                "Failed to load component bad_component: "
                "No module named 'viseron.components.bad_component'"
            ),
        ),
    ],
)
def test_setup_components(vis, config, loaded, loading, failed, caplog, caplog_text):
    """Test setup_components."""
    setup_components(vis, config)
    assert vis.data[LOADED] == loaded
    assert vis.data[LOADING] == loading
    assert vis.data[FAILED] == failed
    if caplog_text:
        assert caplog_text in caplog.text
        caplog.clear()


def test_broken_config_schema(vis, caplog):
    """Test broken config schema."""
    component = Component(vis, "viseron.components.logger", "logger")
    mock = Mock(side_effect=ValueError("testing"))
    with patch("viseron.components.logger.CONFIG_SCHEMA", new=mock):
        component.setup_component(CONFIG)
    assert "ValueError: testing" in caplog.text
    assert "Unknown error calling logger CONFIG_SCHEMA" in caplog.text
