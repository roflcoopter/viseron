"""Test component module."""
from unittest.mock import ANY, Mock, call, patch

import pytest

from viseron.components import (
    CORE_COMPONENTS,
    DEFAULT_COMPONENTS,
    Component,
    setup_component,
    setup_components,
)
from viseron.const import FAILED, LOADED, LOADING
from viseron.domain_registry import DomainState

from tests.common import MockComponent
from tests.conftest import MockViseron


def test_setup_components(vis: MockViseron, caplog):
    """Test setup of core and default components."""
    setup_components(vis, {"logger": {}})
    for component in CORE_COMPONENTS:
        assert component in vis.data[LOADED]

    for component in DEFAULT_COMPONENTS:
        assert component in vis.data[LOADED]
    vis.shutdown()


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
            calls.append(call(vis, ANY))
        calls.append(call(vis, ANY))

        mock_setup_component.assert_has_calls(calls, True)
        mock_get_component.assert_called_with(vis, "mqtt", {"mqtt": {}})


@pytest.mark.parametrize(
    "component, loaded, loading, failed",
    [
        (
            "logger",
            True,
            False,
            False,
        ),
        (
            "logger",
            False,
            False,
            True,
        ),
    ],
)
def test_setup_component(
    vis,
    component,
    loaded,
    loading,
    failed,
):
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


def test_domain_setup_status(vis):
    """Test domain registry state transitions."""
    registry = vis.domain_registry

    registry.register(
        component_name="test_component",
        component_path="viseron.components.test_component",
        domain="object_detector",
        identifier="identifier1",
        config={},
        require_domains=[],
        optional_domains=[],
    )

    # Initially should be PENDING
    entry = registry.get("object_detector", "identifier1")
    assert entry is not None
    assert entry.state == DomainState.PENDING

    registry.set_state("object_detector", "identifier1", DomainState.LOADING)
    entry = registry.get("object_detector", "identifier1")
    assert entry.state == DomainState.LOADING

    registry.set_state("object_detector", "identifier1", DomainState.LOADED)
    entry = registry.get("object_detector", "identifier1")
    assert entry.state == DomainState.LOADED


def test_domain_setup_status_failed(vis):
    """Test failed domain registry state."""
    registry = vis.domain_registry

    registry.register(
        component_name="test_component",
        component_path="viseron.components.test_component",
        domain="object_detector",
        identifier="identifier1",
        config={},
        require_domains=[],
        optional_domains=[],
    )

    registry.set_state("object_detector", "identifier1", DomainState.LOADING)
    registry.set_state(
        "object_detector", "identifier1", DomainState.FAILED, error="Test error"
    )

    entry = registry.get("object_detector", "identifier1")
    assert entry.state == DomainState.FAILED
    assert entry.error == "Test error"


class TestComponent:
    """Test Component class."""

    def test_add_domain_to_setup(self, vis, caplog):
        """Test add_domain_to_setup."""
        registry = vis.domain_registry

        component1 = Component(vis, "component1", "component1", {})
        component1.add_domain_to_setup("object_detector", {}, "identifier1", None, None)

        entry = registry.get("object_detector", "identifier1")
        assert entry is not None
        assert entry.component_name == "component1"

        # Assert that the same domain and identifier can't be added by another component
        component2 = Component(vis, "component2", "component2", {})
        component2.add_domain_to_setup("object_detector", {}, "identifier1", None, None)

        entry = registry.get("object_detector", "identifier1")
        assert entry.component_name == "component1"
        assert (
            "Domain object_detector with identifier identifier1 already in setup "
            "queue. Skipping setup of domain object_detector with identifier "
            "identifier1 for component component2" in caplog.text
        )
        caplog.clear()
