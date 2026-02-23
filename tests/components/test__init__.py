"""Test component module."""
from __future__ import annotations

import logging
from typing import Literal
from unittest.mock import ANY, Mock, call, patch

import pytest
import voluptuous as vol

from viseron.components import (
    CORE_COMPONENTS,
    DEFAULT_COMPONENTS,
    LOGGING_COMPONENTS,
    Component,
    CriticalComponentsConfigStore,
    activate_safe_mode,
    setup_component,
    setup_components,
)
from viseron.const import FAILED, LOADED, LOADING
from viseron.exceptions import ComponentNotReady

from tests.common import MockComponent, MockComponentModule
from tests.conftest import MockViseron


class TestSetupComponents:
    """Test setup_components function."""

    def test_setup_core_default(self, vis: MockViseron) -> None:
        """Test setup of core and default components."""
        setup_components(vis, {"logger": {}})
        for component in CORE_COMPONENTS:
            assert component in vis.data[LOADED]

        for component in DEFAULT_COMPONENTS:
            assert component in vis.data[LOADED]
        vis.shutdown()

    def test_setup_components(
        self,
        vis: MockViseron,
    ) -> None:
        """Test setup of component."""
        with patch("viseron.components.setup_component") as mock_setup_component, patch(
            "threading.Thread.is_alive"
        ) as mock_is_alive, patch(
            "viseron.components.get_component"
        ) as mock_get_component:
            mock_is_alive.return_value = True
            setup_components(vis, {"mqtt": {}})
            assert (
                mock_setup_component.call_count
                == len(CORE_COMPONENTS) + len(DEFAULT_COMPONENTS) + 1
            )
            calls = []
            for _component in set.union(CORE_COMPONENTS, DEFAULT_COMPONENTS):
                calls.append(call(vis, ANY))
            calls.append(call(vis, ANY, domains_only=False))

            mock_setup_component.assert_has_calls(calls, True)
            mock_get_component.assert_called_with(vis, "mqtt", {"mqtt": {}})

    def test_thread_timeout_logged(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test logs error when thread doesn't finish in time."""

        def mock_setup(
            vis_arg,
            component,
            tries=1,  # pylint: disable=unused-argument
            domains_only=False,  # pylint: disable=unused-argument
        ) -> None:
            vis_arg.data[LOADED][component.name] = component
            if component.name in vis_arg.data.get(LOADING, {}):
                del vis_arg.data[LOADING][component.name]

        with patch("viseron.components.setup_component", side_effect=mock_setup), patch(
            "threading.Thread.is_alive", return_value=True
        ), patch("viseron.components.RestartableThread") as mock_thread_class:
            mock_thread = Mock()
            mock_thread.is_alive.return_value = True
            mock_thread.name = "mqtt_setup"
            mock_thread_class.return_value = mock_thread

            setup_components(vis, {"mqtt": {}})

        assert "did not finish in time" in caplog.text


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
    vis: MockViseron,
    component: Literal["logger"],
    loaded: bool,
    loading: bool,
    failed: bool,
) -> None:
    """Test setup_component."""
    mock_component = MockComponent(
        vis, component, setup_component=lambda *_args, **_kwargs: loaded
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


def test_setup_missing_component(
    vis: MockViseron, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setp of missing component."""
    mock_component = MockComponent(
        vis, "testing", setup_component=Mock(side_effect=ModuleNotFoundError("testing"))
    )
    with patch("viseron.components.Component", new=mock_component):
        setup_component(vis, mock_component)
    assert vis.data[LOADED] == {}
    assert vis.data[LOADING] == {}
    assert vis.data[FAILED] == {"testing": mock_component}
    assert "Failed to load component testing" in caplog.text
    caplog.clear()


class TestComponent:
    """Test Component class."""

    def test_add_domain_to_setup(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ) -> None:
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
        assert entry is not None
        assert entry.component_name == "component1"
        assert (
            "Domain object_detector with identifier identifier1 already in setup "
            "queue. Skipping setup of domain object_detector with identifier "
            "identifier1 for component component2" in caplog.text
        )
        caplog.clear()

    def test_get_component_success(self, vis: MockViseron) -> None:
        """Test get_component imports the module successfully."""
        mock_module = MockComponentModule()
        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ) as mock_import:
            component = Component(vis, "viseron.components.test", "test", {})
            result = component.get_component()

            mock_import.assert_called_once_with("viseron.components.test")
            assert result == mock_module


class TestComponentConfigValidation:
    """Test Component.validate_component_config method."""

    def test_validate_config_no_schema(self, vis: MockViseron) -> None:
        """Test validation when module has no CONFIG_SCHEMA."""
        mock_module = MockComponentModule(config_schema=None)
        component = Component(vis, "test_path", "test", {"key": "value"})

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            result = component.validate_component_config()

        assert result is True

    def test_validate_config_valid_schema(self, vis: MockViseron) -> None:
        """Test validation with valid CONFIG_SCHEMA."""
        validated_config: dict[str, bool] = {"validated": True}

        def schema(_config) -> dict[str, bool]:
            return validated_config

        mock_module = MockComponentModule(config_schema=schema)
        component = Component(vis, "test_path", "test", {"key": "value"})

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            result = component.validate_component_config()

        assert result == validated_config

    def test_validate_config_vol_invalid(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test validation with vol.Invalid exception."""
        mock_module = MockComponentModule(
            config_schema=Mock(side_effect=vol.Invalid("Invalid config value"))
        )
        component = Component(vis, "test_path", "test_comp", {"key": "value"})

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            result = component.validate_component_config()

        assert result is None
        assert "Error validating config for component test_comp" in caplog.text

    def test_validate_config_generic_exception(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test validation with generic exception."""
        mock_module = MockComponentModule(
            config_schema=Mock(side_effect=RuntimeError("Unexpected error"))
        )
        component = Component(vis, "test_path", "test_comp", {"key": "value"})

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            result = component.validate_component_config()

        assert result is None
        assert "Unknown error calling test_comp CONFIG_SCHEMA" in caplog.text


class TestComponentSetup:
    """Test Component.setup_component method."""

    def test_setup_component_success(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test successful component setup."""
        caplog.set_level(logging.DEBUG)
        mock_module = MockComponentModule(setup_return=True)

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            component = Component(vis, "viseron.components.test", "test", {})
            result: bool = component.setup_component()

            assert result is True
            assert "Setting up component test" in caplog.text
            assert "Setup of component test took" in caplog.text

    def test_setup_component_failure(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test component setup that returns False."""
        mock_module = MockComponentModule(setup_return=False)

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            component = Component(vis, "viseron.components.test", "test", {})
            result: bool = component.setup_component()

            assert result is False
            assert "Setup of component test failed" in caplog.text

    def test_setup_component_non_boolean_return(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test component setup that returns non-boolean."""
        mock_module = MockComponentModule(setup_return="not a boolean")

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            component = Component(vis, "viseron.components.test", "test", {})
            result: bool = component.setup_component()

            assert result is False
            assert "Setup of component test did not return boolean" in caplog.text

    def test_setup_component_not_ready_creates_retry_timer(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test ComponentNotReady creates a retry timer."""
        mock_module = MockComponentModule(
            setup_exception=ComponentNotReady("Not ready yet")
        )

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ), patch("viseron.components.NamedTimer") as mock_named_timer:
            component = Component(vis, "viseron.components.test", "test", {})
            result: bool = component.setup_component(tries=1)

            # Setup returns False but schedules a retry
            assert result is False
            assert "Component test is not ready" in caplog.text
            assert "Retrying in" in caplog.text

            # Verify NamedTimer was created for retry
            mock_named_timer.assert_called()

            # Verify shutdown handler was registered
            vis.register_signal_handler.assert_called()

    def test_setup_component_not_ready_shutdown_aborts(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test ComponentNotReady aborts when shutdown is set."""
        mock_module = MockComponentModule(
            setup_exception=ComponentNotReady("Not ready")
        )
        # Set the shutdown event to simulate shutdown in progress
        vis.shutdown_event.set()

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            component = Component(vis, "viseron.components.test", "test", {})
            result: bool = component.setup_component()

            assert result is False
            assert "setup aborted due to shutdown" in caplog.text

    def test_setup_component_uncaught_exception(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test uncaught exception during setup."""
        mock_module = MockComponentModule(
            setup_exception=RuntimeError("Unexpected crash")
        )

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            component = Component(vis, "viseron.components.test", "test", {})
            result: bool = component.setup_component()

            assert result is False
            assert "Uncaught exception setting up component test" in caplog.text

    def test_setup_component_clears_pending_domains_on_failure(
        self, vis: MockViseron
    ) -> None:
        """Test that failed setup clears pending domains."""
        mock_module = MockComponentModule(setup_return=False)

        # Register a pending domain for this component
        vis.domain_registry.register(
            component_name="test",
            component_path="viseron.components.test",
            domain="camera",
            identifier="cam1",
            config={},
            require_domains=[],
            optional_domains=[],
        )

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            component = Component(vis, "viseron.components.test", "test", {})
            result: bool = component.setup_component()

            assert result is False
            # Domain should be unregistered
            assert vis.domain_registry.get("camera", "cam1") is None

    def test_setup_component_retry_removes_failed_status(
        self, vis: MockViseron
    ) -> None:
        """Test that retry attempt removes component from FAILED dict."""
        mock_module = MockComponentModule(setup_return=True)
        mock_component = MockComponent(vis, "test")
        vis.data[FAILED]["test"] = mock_component

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            component = Component(vis, "viseron.components.test", "test", {})
            # Manually call setup_component to test tries > 1 path
            setup_component(vis, component, tries=2)

            assert "test" not in vis.data[FAILED]
            assert "test" in vis.data[LOADED]


class TestCriticalComponentsConfigStore:
    """Test CriticalComponentsConfigStore class."""

    def test_load_delegates_to_storage(self, vis: MockViseron) -> None:
        """Test load() delegates to internal storage."""
        with patch("viseron.components.Storage") as mock_storage_class:
            mock_storage = Mock()
            mock_storage.load.return_value = {"logger": {"level": "debug"}}
            mock_storage_class.return_value = mock_storage

            store = CriticalComponentsConfigStore(vis)
            result = store.load()

            assert result == {"logger": {"level": "debug"}}
            mock_storage.load.assert_called_once()

    def test_save_filters_critical_components(self, vis: MockViseron) -> None:
        """Test save() only saves critical components."""
        with patch("viseron.components.Storage") as mock_storage_class:
            mock_storage = Mock()
            mock_storage_class.return_value = mock_storage

            store = CriticalComponentsConfigStore(vis)

            full_config = {
                "logger": {"level": "debug"},
                "storage": {"path": "/data"},
                "webserver": {"port": 8888},
                "data_stream": {},
                "mqtt": {"host": "localhost"},  # Not critical
                "ffmpeg": {},  # Not critical
            }
            store.save(full_config)

            # Should only save critical components
            saved_config = mock_storage.save.call_args[0][0]
            assert "logger" in saved_config
            assert "storage" in saved_config
            assert "webserver" in saved_config
            assert "data_stream" in saved_config
            assert "mqtt" not in saved_config
            assert "ffmpeg" not in saved_config


class TestActivateSafeMode:
    """Test activate_safe_mode function."""

    def test_sets_safe_mode_true(self, vis: MockViseron) -> None:
        """Test activate_safe_mode sets vis.safe_mode to True."""
        vis.critical_components_config_store = Mock()
        vis.critical_components_config_store.load.return_value = {}

        with patch("viseron.components.setup_component"), patch(
            "viseron.components.get_component"
        ):
            activate_safe_mode(vis)

        assert vis.safe_mode is True

    def test_logs_warning_when_no_config(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test logs warning when no last known good config."""
        vis.critical_components_config_store = Mock()
        vis.critical_components_config_store.load.return_value = {}

        with patch("viseron.components.setup_component"), patch(
            "viseron.components.get_component"
        ):
            activate_safe_mode(vis)

        assert "No last known good config for critical components" in caplog.text

    def test_only_sets_up_non_loaded_components(self, vis: MockViseron) -> None:
        """Test only sets up components not already loaded."""
        vis.critical_components_config_store = Mock()
        vis.critical_components_config_store.load.return_value = {"logger": {}}
        vis.data[LOADED] = {"logger": Mock()}  # Already loaded

        with patch("viseron.components.setup_component"), patch(
            "viseron.components.get_component"
        ) as mock_get:
            activate_safe_mode(vis)

            # Logger should not be set up again
            for call_args in mock_get.call_args_list:
                assert call_args[0][1] != "logger"

    def test_sets_up_missing_critical_components(self, vis) -> None:
        """Test sets up all missing critical components."""
        vis.critical_components_config_store = Mock()
        vis.critical_components_config_store.load.return_value = {}
        vis.data[LOADED] = {}

        setup_calls = []

        def track_setup(vis_arg, component) -> None:
            setup_calls.append(component.name)
            vis_arg.data[LOADED][component.name] = component

        def make_mock_component(
            vis, comp_name, config  # pylint: disable=unused-argument
        ) -> Mock:
            mock_comp = Mock()
            mock_comp.name = comp_name
            return mock_comp

        with patch(
            "viseron.components.setup_component", side_effect=track_setup
        ), patch("viseron.components.get_component", side_effect=make_mock_component):
            activate_safe_mode(vis)

        # All critical components should have been set up
        expected = LOGGING_COMPONENTS | CORE_COMPONENTS | DEFAULT_COMPONENTS
        for comp in expected:
            assert comp in setup_calls


class TestSetupComponentsSafeMode:
    """Test setup_components safe mode."""

    def test_returns_early_when_already_safe_mode(self, vis: MockViseron) -> None:
        """Test returns early when vis.safe_mode is already True."""
        vis.safe_mode = True

        with patch("viseron.components.setup_component") as mock_setup:
            setup_components(vis, {"mqtt": {}})

            # Should only set up critical components, not mqtt
            for call_args in mock_setup.call_args_list:
                component = call_args[0][1]
                assert component.name in (
                    LOGGING_COMPONENTS | CORE_COMPONENTS | DEFAULT_COMPONENTS
                )

    def test_activates_safe_mode_when_critical_fails(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test activates safe mode when critical component fails."""

        def mock_setup(
            vis_arg,
            component,
            tries=1,  # pylint: disable=unused-argument
            domains_only=False,  # pylint: disable=unused-argument
        ) -> None:
            if component.name == "storage":
                vis_arg.data[FAILED][component.name] = component
            else:
                vis_arg.data[LOADED][component.name] = component
            if component.name in vis_arg.data.get(LOADING, {}):
                del vis_arg.data[LOADING][component.name]

        vis.critical_components_config_store = Mock()
        vis.critical_components_config_store.load.return_value = {}

        with patch("viseron.components.setup_component", side_effect=mock_setup):
            setup_components(vis, {"logger": {}})

        assert "Critical components failed to load" in caplog.text
        assert vis.safe_mode is True


class TestEndToEndStateTransitions:
    """Test component lifecycle state transitions."""

    def test_component_loading_to_loaded(self, vis: MockViseron) -> None:
        """Test component transitions from LOADING to LOADED."""
        mock_module = MockComponentModule(setup_return=True)

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            component = Component(vis, "viseron.components.test", "test", {})
            setup_component(vis, component)

        assert "test" in vis.data[LOADED]
        assert "test" not in vis.data[LOADING]
        assert "test" not in vis.data[FAILED]

    def test_component_loading_to_failed(self, vis: MockViseron) -> None:
        """Test component transitions from LOADING to FAILED."""
        mock_module = MockComponentModule(setup_return=False)

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_module
        ):
            component = Component(vis, "viseron.components.test", "test", {})
            setup_component(vis, component)

        assert "test" not in vis.data[LOADED]
        assert "test" not in vis.data[LOADING]
        assert "test" in vis.data[FAILED]
