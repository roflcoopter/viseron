"""Test component module."""
from unittest.mock import Mock, call, patch

import pytest

from viseron.components import (
    CORE_COMPONENTS,
    DEFAULT_COMPONENTS,
    setup_component,
    setup_components,
)
from viseron.const import FAILED, LOADED, LOADING

from tests.common import MockComponent, return_any


def test_setup_components(vis, caplog):
    """Test setup of core and default components."""
    setup_components(vis, {"logger": {}})
    for component in CORE_COMPONENTS:
        assert component in vis.data[LOADED]

    for component in DEFAULT_COMPONENTS:
        assert component in vis.data[LOADED]


def test_setup_components_2(vis, caplog):
    """Test setup of component."""
    with patch("viseron.components.setup_component") as mock_setup_component, patch(
        "threading.Thread.is_alive"
    ) as mock_is_alive, patch("viseron.components.get_component") as mock_get_component:
        mock_is_alive.return_value = True
        setup_components(vis, {"mqtt": {}})
        assert (
            mock_setup_component.call_count
            == len(CORE_COMPONENTS) + len(DEFAULT_COMPONENTS) + 1
        )
        calls = []
        for _component in set.union(CORE_COMPONENTS, DEFAULT_COMPONENTS):
            calls.append(call(vis, return_any(object)))
        calls.append(call(vis, return_any(object)))

        mock_setup_component.assert_has_calls(calls, True)
        mock_get_component.assert_called_with(vis, "mqtt", {"mqtt": {}})


@pytest.mark.parametrize(
    "component, loaded, loading, failed, caplog_text",
    [
        (
            "logger",
            True,
            False,
            False,
            None,
        ),
        (
            "logger",
            False,
            False,
            True,
            ("Failed setup of component logger"),
        ),
    ],
)
def test_setup_component(vis, component, loaded, loading, failed, caplog, caplog_text):
    """Test setup_component."""
    mock_component = MockComponent(
        component, setup_component=lambda *_args, **_kwargs: loaded
    )
    with patch("viseron.components.Component", new=mock_component):
        setup_component(vis, mock_component)

    if loaded:
        assert vis.data[LOADED] == {component: mock_component}
    else:
        assert vis.data[LOADED] == {}
    if loading:
        assert vis.data[LOADING] == {component: mock_component}
    else:
        assert vis.data[LOADING] == {}
    if failed:
        assert vis.data[FAILED] == {component: mock_component}
    else:
        assert vis.data[FAILED] == {}
    if caplog_text:
        assert caplog_text in caplog.text
        caplog.clear()


def test_setup_missing_component(vis, caplog):
    """Test setp of missing component."""
    mock_component = MockComponent(
        "testing", setup_component=Mock(side_effect=ModuleNotFoundError("testing"))
    )
    with patch("viseron.components.Component", new=mock_component):
        setup_component(vis, mock_component)
    assert vis.data[LOADED] == {}
    assert vis.data[LOADING] == {}
    assert vis.data[FAILED] == {"testing": mock_component}
    assert "Failed to load component testing" in caplog.text
    caplog.clear()
