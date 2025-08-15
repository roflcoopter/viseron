"""Tests for viseron.helpers.template."""
from types import SimpleNamespace

import pytest
from jinja2 import Environment

from viseron.helpers.template import (
    StateNamespace,
    _DomainNamespace,
    render_template,
    render_template_condition,
)

from tests.conftest import MockViseron


class DummyStates:
    """Dummy states for testing."""

    def __init__(self, states):
        self.current = states


def test_state_namespace_getattr_and_getitem():
    """Test StateNamespace and _DomainNamespace attribute and item access."""
    states = {
        "binary_sensor.camera_1": SimpleNamespace(state="on"),
        "camera.camera_2": SimpleNamespace(state="off"),
    }
    ns = StateNamespace(states)
    # Attribute access returns _DomainNamespace
    binary_sensor_ns = ns.binary_sensor
    assert isinstance(binary_sensor_ns, _DomainNamespace)
    # Item access returns the state object
    assert ns["binary_sensor.camera_1"].state == "on"
    assert ns["camera.camera_2"].state == "off"
    # _DomainNamespace attribute and item access
    assert binary_sensor_ns.camera_1.state == "on"
    assert binary_sensor_ns["camera_1"].state == "on"
    camera_ns = ns.camera
    assert camera_ns.camera_2.state == "off"
    assert camera_ns["camera_2"].state == "off"


def test_state_namespace_missing_key():
    """Test StateNamespace and _DomainNamespace raise KeyError for missing keys."""
    states = {"sensor.x": SimpleNamespace(state="ok")}
    ns = StateNamespace(states)
    with pytest.raises(KeyError):
        _ = ns["sensor.y"]
    with pytest.raises(KeyError):
        _ = ns.sensor.y
    with pytest.raises(KeyError):
        _ = ns.sensor["y"]


def test_render_template_valid_and_empty(vis: MockViseron):
    """Test render_template with valid template, empty template, and extra kwargs."""
    vis.states._current_states = {  # pylint: disable=protected-access
        "sensor.temp": SimpleNamespace(state="23"),  # type: ignore[dict-item]
        "switch.light": SimpleNamespace(state="on"),  # type: ignore[dict-item]
    }
    env = Environment()
    # Valid template
    tpl = (
        "Sensor is {{ states.sensor.temp.state }} "
        "and switch is {{ states.switch.light.state }}."
    )
    result = render_template(vis, env, tpl)
    assert result == "Sensor is 23 and switch is on."
    # With extra kwargs
    tpl2 = "Value: {{ value }}"
    result2 = render_template(vis, env, tpl2, value=42)
    assert result2 == "Value: 42"
    # Empty template
    assert render_template(vis, env, "") is None
    assert render_template(vis, env, None) is None


@pytest.mark.parametrize(
    "template",
    [
        ("True"),
        ("yes"),
        ("on"),
        ("enable"),
        ("{{ true }}"),
        ("{{ True }}"),
        ("{{ 1 }}"),
        ("{{ states.sensor.x.state }}"),
        ("{{ states.sensor.x.state == 'on' }}"),
    ],
)
def test_render_template_condition_truthy(vis: MockViseron, template):
    """Test render_template_condition for all truthy outputs."""
    vis.states._current_states = {  # pylint: disable=protected-access
        "sensor.x": SimpleNamespace(state="on"),  # type: ignore[dict-item]
    }
    env = Environment()
    result, _ = render_template_condition(vis, env, template)
    assert result is True


@pytest.mark.parametrize(
    "template",
    [
        ("False"),
        ("no"),
        ("off"),
        ("disable"),
        ("{{ false }}"),
        ("{{ False }}"),
        ("{{ 0 }}"),
        ("{{ -1 }}"),
        ("{{ states.sensor.x.state == 'off' }}"),
        ("random text"),
    ],
)
def test_render_template_condition_false(vis: MockViseron, template):
    """Test render_template_condition for all false outputs."""
    vis.states._current_states = {  # pylint: disable=protected-access
        "sensor.x": SimpleNamespace(state="on"),  # type: ignore[dict-item]
    }
    env = Environment()
    result, _ = render_template_condition(vis, env, template)
    assert result is False


def test_render_template_missing_state_raises(vis: MockViseron):
    """Test that render_template raises KeyError if state is missing."""
    vis.states._current_states = {  # pylint: disable=protected-access
        "sensor.x": SimpleNamespace(state="on"),  # type: ignore[dict-item]
    }
    env = Environment()
    tpl = "{{ states.sensor.y.state }}"
    with pytest.raises(KeyError):
        render_template(vis, env, tpl)
