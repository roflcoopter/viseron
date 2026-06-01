"""Tests for domains module."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from logging import DEBUG
from typing import TYPE_CHECKING, Any, Literal
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

from viseron.domain_registry import DomainEntry, DomainState
from viseron.domains import (
    OptionalDomain,
    RequireDomain,
    _handle_failed_domain,
    _schedule_domain_setup,
    _setup_single_domain,
    _submit_domain_setup,
    _wait_for_dependencies,
    get_unload_order,
    setup_domains,
    unload_domain,
    unload_domain_chain,
    unload_domain_identifier,
)
from viseron.exceptions import DomainNotReady

from tests.common import MockComponent, MockDomainModule

if TYPE_CHECKING:
    from viseron.viseron_types import SupportedDomains

    from tests.conftest import MockViseron


class TestGetUnloadOrder:
    """Test get_unload_order function."""

    def test_single_domain_no_dependents(self, vis: MockViseron):
        """Test unload order for a single domain with no dependents."""
        registry = vis.domain_registry

        # Register and load a single domain
        registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        result = get_unload_order(vis, "camera", "cam1")

        assert len(result) == 1
        assert result[0].domain == "camera"
        assert result[0].identifier == "cam1"

    def test_domain_with_multiple_dependents(self, vis: MockViseron):
        """Test unload order with multiple dependent domains."""
        registry = vis.domain_registry

        # Register base domain
        registry.register(
            component_name="camera_comp",
            component_path="camera.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        # Register first dependent (nvr)
        registry.register(
            component_name="nvr_comp",
            component_path="nvr.path",
            domain="nvr",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("camera", "cam1")],
        )
        registry.set_state("nvr", "cam1", DomainState.LOADED)

        # Register second dependent (object_detector)
        registry.register(
            component_name="detector_comp",
            component_path="detector.path",
            domain="object_detector",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("camera", "cam1")],
        )
        registry.set_state("object_detector", "cam1", DomainState.LOADED)

        result = get_unload_order(vis, "camera", "cam1")

        # Both dependents should come before camera
        assert len(result) == 3
        domains = [e.domain for e in result]
        assert domains[-1] == "camera"  # Camera should be last
        assert "nvr" in domains[:2]
        assert "object_detector" in domains[:2]

    def test_chain_of_dependents(self, vis: MockViseron):
        """Test unload order with a chain of dependencies."""
        registry = vis.domain_registry

        # Register camera (base)
        registry.register(
            component_name="camera_comp",
            component_path="camera.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        # Register object_detector (depends on camera)
        registry.register(
            component_name="detector_comp",
            component_path="detector.path",
            domain="object_detector",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("camera", "cam1")],
        )
        registry.set_state("object_detector", "cam1", DomainState.LOADED)

        # Register nvr (depends on object_detector)
        registry.register(
            component_name="nvr_comp",
            component_path="nvr.path",
            domain="nvr",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("object_detector", "cam1")],
        )
        registry.set_state("nvr", "cam1", DomainState.LOADED)

        result = get_unload_order(vis, "camera", "cam1")

        # Order should be: nvr -> object_detector -> camera
        assert len(result) == 3
        assert result[0].domain == "nvr"
        assert result[1].domain == "object_detector"
        assert result[2].domain == "camera"

    def test_nonexistent_domain(self, vis: MockViseron):
        """Test unload order for a domain that doesn't exist."""
        result = get_unload_order(vis, "nonexistent", "id1")  # type: ignore[arg-type]

        assert len(result) == 0

    @pytest.mark.parametrize(
        ("target_domain", "target_id", "expected_count"),
        [
            ("camera", "cam1", 2),  # nvr depends on cam1
            ("camera", "cam2", 1),  # No dependents on cam2
            ("nvr", "cam1", 1),  # nvr itself, no dependents
        ],
    )
    def test_different_identifiers(
        self,
        vis: MockViseron,
        target_domain: SupportedDomains,
        target_id: str,
        expected_count: int,
    ):
        """Test that identifier matching works correctly."""
        registry = vis.domain_registry

        # Register two cameras
        for cam_id in ["cam1", "cam2"]:
            registry.register(
                component_name="camera_comp",
                component_path="camera.path",
                domain="camera",
                identifier=cam_id,
                config={},
            )
            registry.set_state("camera", cam_id, DomainState.LOADED)

        # nvr only depends on cam1
        registry.register(
            component_name="nvr_comp",
            component_path="nvr.path",
            domain="nvr",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("camera", "cam1")],
        )
        registry.set_state("nvr", "cam1", DomainState.LOADED)

        result = get_unload_order(vis, target_domain, target_id)

        assert len(result) == expected_count

    def test_optional_domain_dependency(self, vis: MockViseron):
        """Test that optional dependencies are also included in unload order."""
        registry = vis.domain_registry

        # Register base domain
        registry.register(
            component_name="camera_comp",
            component_path="camera.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        # Register domain with optional dependency
        registry.register(
            component_name="detector_comp",
            component_path="detector.path",
            domain="object_detector",
            identifier="cam1",
            config={},
            optional_domains=[OptionalDomain("camera", "cam1")],
        )
        registry.set_state("object_detector", "cam1", DomainState.LOADED)

        result = get_unload_order(vis, "camera", "cam1")

        # object_detector (optional dependent) should come before camera
        assert len(result) == 2
        assert result[0].domain == "object_detector"
        assert result[1].domain == "camera"


class TestUnloadDomainIdentifier:
    """Test unload_domain_identifier function."""

    def test_unload_domain_success(self, vis: MockViseron):
        """Test successful domain unload."""
        # Create mock instance with unload method
        mock_instance = Mock()
        mock_instance.unload = Mock()

        registry = vis.domain_registry
        registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)
        registry.set_instance("camera", "cam1", mock_instance)

        result = unload_domain_identifier(vis, "camera", "cam1")
        assert result is not None
        assert result.domain == "camera"
        assert result.identifier == "cam1"
        assert registry.get("camera", "cam1") is None
        mock_instance.unload.assert_called_once()

    def test_unload_without_unload_method(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ):
        """Test unload succeeds even if domain has no unload method."""
        caplog.set_level(DEBUG)
        # Create mock instance without unload method
        mock_instance = Mock(spec=[])

        registry = vis.domain_registry
        registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)
        registry.set_instance("camera", "cam1", mock_instance)

        result = unload_domain_identifier(vis, "camera", "cam1")
        assert result is not None
        assert result.domain == "camera"
        assert result.identifier == "cam1"
        assert registry.get("camera", "cam1") is None
        assert "Domain camera with identifier cam1 has no unload method" in caplog.text

    def test_unload_handles_unload_exception(self, vis: MockViseron):
        """Test that exceptions in unload method are handled gracefully."""
        # Create mock instance that raises exception
        mock_instance = Mock()
        mock_instance.unload = Mock(side_effect=RuntimeError("Unload failed"))

        registry = vis.domain_registry
        registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)
        registry.set_instance("camera", "cam1", mock_instance)

        result = unload_domain_identifier(vis, "camera", "cam1")
        assert result is not None
        assert registry.get("camera", "cam1") is None
        mock_instance.unload.assert_called_once()

    def test_unload_removes_entities(self, vis: MockViseron):
        """Test that entities are removed during unload."""
        # Set up entity ownership structure
        vis.states._register_entity_owner(
            "test_comp",
            "entity.test1",
            "camera",
            "cam1",
        )
        vis.states._register_entity_owner(
            "test_comp",
            "entity.test2",
            "camera",
            "cam1",
        )

        registry = vis.domain_registry
        registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        with patch.object(vis.states, "unload_entity") as mock_unload_entity:
            unload_domain_identifier(vis, "camera", "cam1")
            assert mock_unload_entity.call_count == 2
            mock_unload_entity.assert_any_call("entity.test1")
            mock_unload_entity.assert_any_call("entity.test2")

    @pytest.mark.parametrize(
        "entity_structure",
        [
            {},  # No component entry
            {"test_comp": {}},  # No domains entry
            {"test_comp": {"domains": {}}},  # No camera domain
            {"test_comp": {"domains": {"camera": {}}}},  # No identifiers
            {"test_comp": {"domains": {"camera": {"identifiers": {}}}}},  # No cam1
        ],
    )
    def test_unload_handles_missing_entity_structure(
        self, vis: MockViseron, entity_structure: dict[str, Any]
    ):
        """Test unload handles missing or incomplete entity structures."""
        vis.states._entity_owner = entity_structure

        registry = vis.domain_registry
        registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        with patch.object(vis.states, "unload_entity") as mock_unload_entity:
            result = unload_domain_identifier(vis, "camera", "cam1")
            assert result is not None
            mock_unload_entity.assert_not_called()

    def test_unload_with_no_instance(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ):
        """Test unload succeeds when entry has no instance."""
        caplog.set_level(DEBUG)

        registry = vis.domain_registry
        registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        result = unload_domain_identifier(vis, "camera", "cam1")
        assert result is not None
        assert registry.get("camera", "cam1") is None
        assert "Domain camera with identifier cam1 has no unload method" in caplog.text

    def test_unload_nonexistent_domain_returns_none(
        self,
        vis: MockViseron,
    ):
        """Test that unloading a domain that doesn't exist returns None."""
        result = unload_domain_identifier(vis, "camera", "nonexistent")
        assert result is None

    def test_unload_cancels_retry(self, vis: MockViseron):
        """Test that cancel_retry is called during unload."""
        registry = vis.domain_registry
        registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.RETRYING)

        with patch.object(registry, "cancel_retry") as mock_cancel:
            unload_domain_identifier(vis, "camera", "cam1")
            mock_cancel.assert_called_once_with("camera", "cam1")


class TestUnloadDomainChain:
    """Test unload_domain_chain function."""

    def test_returns_affected_components(self, vis: MockViseron):
        """Test that only dependent component names are returned, not the root's."""
        registry = vis.domain_registry
        registry.register(
            component_name="camera_comp",
            component_path="camera.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        registry.register(
            component_name="nvr_comp",
            component_path="nvr.path",
            domain="nvr",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("camera", "cam1")],
        )
        registry.set_state("nvr", "cam1", DomainState.LOADED)

        affected = unload_domain_chain(vis, "camera", "cam1")

        # camera_comp owns the root domain being unloaded and is intentionally excluded.
        assert affected == {"nvr_comp"}
        assert registry.get("camera", "cam1") is None
        assert registry.get("nvr", "cam1") is None

    def test_unloads_in_dependents_first_order(self, vis: MockViseron):
        """Test that dependents are unloaded before their dependency."""
        unloaded_order: list[str] = []

        registry = vis.domain_registry
        registry.register(
            component_name="camera_comp",
            component_path="camera.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        registry.register(
            component_name="nvr_comp",
            component_path="nvr.path",
            domain="nvr",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("camera", "cam1")],
        )
        registry.set_state("nvr", "cam1", DomainState.LOADED)

        original_unregister = registry.unregister

        def _tracking_unregister(domain: str, identifier: str) -> DomainEntry | None:
            unloaded_order.append(domain)
            return original_unregister(domain, identifier)

        with patch.object(registry, "unregister", side_effect=_tracking_unregister):
            unload_domain_chain(vis, "camera", "cam1")

        assert unloaded_order == ["nvr", "camera"]

    def test_nonexistent_domain_returns_empty_set(self, vis: MockViseron):
        """Test that a nonexistent domain returns an empty set."""
        affected = unload_domain_chain(
            vis,
            "camera",
            "nonexistent",
        )
        assert affected == set()


class TestUnloadDomain:
    """Test unload_domain function."""

    def _register_domain(
        self,
        vis: MockViseron,
        component_name: str = "test_comp",
        domain: SupportedDomains = "camera",
        identifier: str = "cam1",
    ) -> None:
        vis.domain_registry.register(
            component_name=component_name,
            component_path=f"viseron.components.{component_name}",
            domain=domain,
            identifier=identifier,
            config={},
        )
        vis.domain_registry.set_state(domain, identifier, DomainState.LOADED)

    def test_returns_none_when_component_not_found(self, vis: MockViseron):
        """Test that None is returned when the component is not in LOADED."""
        result = unload_domain(vis, "nonexistent_comp", "camera")
        assert result is None

    def test_unloads_all_identifiers_for_domain(self, vis: MockViseron):
        """Test that every identifier belonging to the component/domain is unloaded."""
        MockComponent(vis, "test_comp")
        self._register_domain(vis, identifier="cam1")
        self._register_domain(vis, identifier="cam2")

        with patch(
            "viseron.domains.importlib.import_module",
            side_effect=ModuleNotFoundError,
        ):
            result = unload_domain(vis, "test_comp", "camera")

        assert result is not None
        assert vis.domain_registry.get("camera", "cam1") is None
        assert vis.domain_registry.get("camera", "cam2") is None

    def test_returns_affected_components(self, vis: MockViseron):
        """Test that only dependent component names are returned."""
        MockComponent(vis, "test_comp")
        self._register_domain(vis, identifier="cam1")

        # Register a dependent in another component
        vis.domain_registry.register(
            component_name="nvr_comp",
            component_path="viseron.components.nvr_comp",
            domain="nvr",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("camera", "cam1")],
        )
        vis.domain_registry.set_state("nvr", "cam1", DomainState.LOADED)

        with patch(
            "viseron.domains.importlib.import_module",
            side_effect=ModuleNotFoundError,
        ):
            result = unload_domain(vis, "test_comp", "camera")

        assert result is not None
        assert "test_comp" not in result
        assert "nvr_comp" in result

    def test_calls_domain_module_unload(self, vis: MockViseron):
        """Test that the domain module's unload() is called if it exists."""
        MockComponent(vis, "test_comp")
        self._register_domain(vis, identifier="cam1")

        unload_called: list[bool] = []

        mock_module = Mock()
        mock_module.unload = lambda _vis: unload_called.append(True)

        with patch("viseron.domains.importlib.import_module", return_value=mock_module):
            unload_domain(vis, "test_comp", "camera")

        assert unload_called, "domain module's unload() was not called"

    def test_no_domain_module_unload_method(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ):
        """Test that missing unload() on domain module is handled gracefully."""
        caplog.set_level(DEBUG)
        MockComponent(vis, "test_comp")
        self._register_domain(vis, identifier="cam1")

        mock_module = Mock(spec=[])  # no unload attribute

        with patch("viseron.domains.importlib.import_module", return_value=mock_module):
            result = unload_domain(vis, "test_comp", "camera")

        assert result is not None
        assert "has no unload method" in caplog.text

    def test_domain_module_unload_exception_is_handled(self, vis: MockViseron):
        """Test that an exception in domain module unload() doesn't propagate."""
        MockComponent(vis, "test_comp")
        self._register_domain(vis, identifier="cam1")

        mock_module = Mock()
        mock_module.unload = Mock(side_effect=RuntimeError("unload boom"))

        with patch("viseron.domains.importlib.import_module", return_value=mock_module):
            result = unload_domain(vis, "test_comp", "camera")  # must not raise

        assert result is not None

    def test_module_not_found_returns_affected_components(self, vis: MockViseron):
        """Test that a missing domain module still returns accumulated affected set."""
        MockComponent(vis, "test_comp")
        self._register_domain(vis, identifier="cam1")

        with patch(
            "viseron.domains.importlib.import_module",
            side_effect=ModuleNotFoundError("no module"),
        ):
            result = unload_domain(vis, "test_comp", "camera")

        # Should return what was collected, not None
        assert result is not None
        assert isinstance(result, set)

    def test_no_identifiers_returns_empty_set(self, vis: MockViseron):
        """Test that a component with no registered identifiers returns an empty set."""
        MockComponent(vis, "test_comp")
        # No domains registered

        mock_module = Mock(spec=[])  # no unload

        with patch("viseron.domains.importlib.import_module", return_value=mock_module):
            result = unload_domain(vis, "test_comp", "camera")

        assert result == set()


class TestHandleFailedDomain:
    """Test _handle_failed_domain function."""

    @pytest.mark.parametrize(
        "state",
        [DomainState.FAILED, DomainState.RETRYING],
    )
    def test_handle_failed_domain_sets_state(
        self, vis: MockViseron, state: Literal[DomainState.FAILED, DomainState.RETRYING]
    ) -> None:
        """Test _handle_failed_domain sets the correct state."""
        vis.domain_registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch("viseron.components.importlib.import_module") as mock_import:
            mock_import.side_effect = ModuleNotFoundError("No domain module")
            _handle_failed_domain(vis, entry, state, error="Test error")

        updated_entry = vis.domain_registry.get("camera", "cam1")
        assert updated_entry is not None
        assert updated_entry.state == state
        assert updated_entry.error == "Test error"

    def test_handle_failed_domain_with_setup_failed_handler(
        self, vis: MockViseron
    ) -> None:
        """Test _handle_failed_domain calls setup_failed handler."""
        error_instance = Mock()

        def setup_failed_handler(_vis_arg: MockViseron, _entry_arg: Mock) -> Mock:
            return error_instance

        mock_domain_module = Mock()
        mock_domain_module.setup_failed = setup_failed_handler

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module",
            return_value=mock_domain_module,
        ):
            _handle_failed_domain(vis, entry, DomainState.FAILED, error="Test error")

        updated_entry = vis.domain_registry.get("camera", "cam1")
        assert updated_entry is not None
        assert updated_entry.error_instance == error_instance

    def test_handle_failed_domain_no_handler(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test _handle_failed_domain when domain module doesn't exist."""
        caplog.set_level(logging.DEBUG)

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="nonexistent_domain",  # type: ignore[arg-type]
            identifier="id1",
            config={},
        )
        entry = vis.domain_registry.get("nonexistent_domain", "id1")
        assert entry is not None

        # Domain module import will fail, triggering the exception handler
        with patch(
            "viseron.components.importlib.import_module",
            side_effect=ModuleNotFoundError("No module"),
        ):
            _handle_failed_domain(vis, entry, DomainState.FAILED, error="Test error")

        updated_entry = vis.domain_registry.get("nonexistent_domain", "id1")
        assert updated_entry is not None
        assert updated_entry.state == DomainState.FAILED
        assert updated_entry.error_instance is None
        assert "No setup_failed handler" in caplog.text

    def test_handle_failed_domain_no_setup_failed_attr(self, vis: MockViseron) -> None:
        """Test _handle_failed_domain when module exists but has no setup_failed."""
        mock_domain_module = Mock(spec=[])

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module",
            return_value=mock_domain_module,
        ):
            _handle_failed_domain(vis, entry, DomainState.FAILED, error="Test error")

        updated_entry = vis.domain_registry.get("camera", "cam1")
        assert updated_entry is not None
        assert updated_entry.state == DomainState.FAILED
        # No error instance since no handler was called
        assert updated_entry.error_instance is None


class TestWaitForDependencies:
    """Test _wait_for_dependencies function."""

    def test_no_dependencies_returns_true(self, vis: MockViseron) -> None:
        """Test that no dependencies returns True immediately."""
        entry = DomainEntry(
            component_name="test",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
            require_domains=[],
            optional_domains=[],
        )

        result: bool = _wait_for_dependencies(vis, entry)
        assert result is True

    def test_required_dependency_already_loaded(self, vis: MockViseron) -> None:
        """Test skips already loaded required dependencies."""
        # Register and mark a dependency as loaded
        vis.domain_registry.register(
            component_name="dep_comp",
            component_path="dep.path",
            domain="object_detector",
            identifier="detector1",
            config={},
        )
        vis.domain_registry.set_state(
            "object_detector", "detector1", DomainState.LOADED
        )

        entry = DomainEntry(
            component_name="test",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("object_detector", "detector1")],
            optional_domains=[],
        )

        result: bool = _wait_for_dependencies(vis, entry)
        assert result is True

    def test_required_dependency_future_success(self, vis: MockViseron) -> None:
        """Test waits for required dependency future to complete."""
        # Register dependency
        vis.domain_registry.register(
            component_name="dep_comp",
            component_path="dep.path",
            domain="object_detector",
            identifier="detector1",
            config={},
        )

        # Create a completed future
        future: Future[bool] = Future()
        future.set_result(True)
        vis.domain_registry.set_future("object_detector", "detector1", future)

        entry = DomainEntry(
            component_name="test",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("object_detector", "detector1")],
            optional_domains=[],
        )

        result: bool = _wait_for_dependencies(vis, entry)
        assert result is True

    def test_required_dependency_future_failure(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test returns False when required dependency fails."""
        vis.domain_registry.register(
            component_name="dep_comp",
            component_path="dep.path",
            domain="object_detector",
            identifier="detector1",
            config={},
        )

        future: Future[bool] = Future()
        future.set_result(False)  # Dependency failed
        vis.domain_registry.set_future("object_detector", "detector1", future)

        entry = DomainEntry(
            component_name="test",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("object_detector", "detector1")],
            optional_domains=[],
        )

        result: bool = _wait_for_dependencies(vis, entry)
        assert result is False
        assert "Unable to setup dependencies for domain camera" in caplog.text

    def test_optional_dependency_not_configured_skipped(self, vis: MockViseron) -> None:
        """Test optional dependency not configured is skipped."""
        entry = DomainEntry(
            component_name="test",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
            require_domains=[],
            optional_domains=[OptionalDomain("motion_detector", "motion1")],
        )

        # Motion detector is not registered, so it should be skipped
        result: bool = _wait_for_dependencies(vis, entry)
        assert result is True

    def test_optional_dependency_configured_awaited(self, vis: MockViseron) -> None:
        """Test optional dependency that is configured is awaited."""
        # Register optional dependency
        vis.domain_registry.register(
            component_name="opt_comp",
            component_path="opt.path",
            domain="motion_detector",
            identifier="motion1",
            config={},
        )

        future: Future[bool] = Future()
        future.set_result(True)
        vis.domain_registry.set_future("motion_detector", "motion1", future)

        entry = DomainEntry(
            component_name="test",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
            require_domains=[],
            optional_domains=[OptionalDomain("motion_detector", "motion1")],
        )

        result: bool = _wait_for_dependencies(vis, entry)
        assert result is True


class TestSetupSingleDomain:
    """Test _setup_single_domain function."""

    def test_setup_domain_success(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test successful domain setup."""
        caplog.set_level(DEBUG)
        mock_domain = MockDomainModule(setup_return=True)

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="viseron.components.test_comp",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_domain
        ):
            result: bool = _setup_single_domain(vis, entry)

            assert result is True
            assert entry.state == DomainState.LOADED
            assert "Setting up domain camera with identifier cam1" in caplog.text
            assert "took" in caplog.text

    def test_setup_domain_module_not_found(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test domain setup when module not found."""
        vis.domain_registry.register(
            component_name="test_comp",
            component_path="viseron.components.test_comp",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module",
            side_effect=ModuleNotFoundError("No module named camera"),
        ):
            result: bool = _setup_single_domain(vis, entry)

            assert result is False
            assert entry.state == DomainState.FAILED
            assert "Failed to load domain module" in caplog.text

    def test_setup_domain_config_vol_invalid(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test domain setup with vol.Invalid config error."""
        mock_domain = MockDomainModule(
            config_schema=lambda c: c,
            config_schema_exception=vol.Invalid("Bad config"),
        )

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="viseron.components.test_comp",
            domain="camera",
            identifier="cam1",
            config={"bad": "config"},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_domain
        ):
            result: bool = _setup_single_domain(vis, entry)

            assert result is False
            assert entry.state == DomainState.FAILED
            assert "Error validating config for domain camera" in caplog.text

    def test_setup_domain_config_generic_exception(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test domain setup with generic config validation exception."""
        mock_domain = MockDomainModule(
            config_schema=lambda c: c,
            config_schema_exception=RuntimeError("Schema crash"),
        )

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="viseron.components.test_comp",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_domain
        ):
            result: bool = _setup_single_domain(vis, entry)

            assert result is False
            assert "Unknown error calling test_comp.camera CONFIG_SCHEMA" in caplog.text

    def test_setup_domain_not_ready_retry_success(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test DomainNotReady triggers retry and eventually succeeds."""
        # First call raises DomainNotReady, second succeeds
        mock_domain = MockDomainModule(
            setup_side_effects=[
                (None, DomainNotReady("Not ready")),
                (True, None),
            ]
        )

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="viseron.components.test_comp",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with (
            patch("viseron.domains.DOMAIN_RETRY_INTERVAL", 0),
            patch(
                "viseron.components.importlib.import_module", return_value=mock_domain
            ),
        ):
            result: bool = _setup_single_domain(vis, entry)

            assert result is True
            assert mock_domain.setup_call_count == 2
            assert "is not ready" in caplog.text
            assert "Retrying in" in caplog.text

    def test_setup_domain_not_ready_shutdown_aborts(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test DomainNotReady aborts retry when shutdown is set."""
        mock_domain = MockDomainModule(setup_exception=DomainNotReady("Not ready"))
        # Set the shutdown event to simulate shutdown in progress
        vis.shutdown_event.set()

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="viseron.components.test_comp",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_domain
        ):
            result: bool = _setup_single_domain(vis, entry)

            assert result is False
            assert "aborted due to shutdown" in caplog.text

    def test_setup_domain_uncaught_exception(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test uncaught exception during domain setup."""
        mock_domain = MockDomainModule(setup_exception=RuntimeError("Unexpected crash"))

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="viseron.components.test_comp",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_domain
        ):
            result: bool = _setup_single_domain(vis, entry)

            assert result is False
            assert entry.state == DomainState.FAILED
            assert "Uncaught exception setting up domain camera" in caplog.text

    def test_setup_domain_returns_false(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test domain setup returning False."""
        mock_domain = MockDomainModule(setup_return=False)

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="viseron.components.test_comp",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_domain
        ):
            result: bool = _setup_single_domain(vis, entry)

            assert result is False
            assert entry.state == DomainState.FAILED
            assert "failed" in caplog.text

    def test_setup_domain_returns_non_boolean(
        self,
        vis: MockViseron,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test domain setup returning non-boolean."""
        mock_domain = MockDomainModule(setup_return="not a bool")

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="viseron.components.test_comp",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_domain
        ):
            result: bool = _setup_single_domain(vis, entry)

            assert result is False
            assert "did not return boolean" in caplog.text

    def test_setup_domain_dependency_failure(
        self,
        vis: MockViseron,
    ) -> None:
        """Test domain setup fails when dependency fails."""
        # Register dependency that will fail
        vis.domain_registry.register(
            component_name="dep_comp",
            component_path="dep.path",
            domain="object_detector",
            identifier="detector1",
            config={},
        )
        dep_future: Future[bool] = Future()
        dep_future.set_result(False)
        vis.domain_registry.set_future("object_detector", "detector1", dep_future)

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="viseron.components.test_comp",
            domain="camera",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("object_detector", "detector1")],
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        result: bool = _setup_single_domain(vis, entry)

        assert result is False
        assert entry.state == DomainState.FAILED
        assert entry.error is not None
        assert "Dependencies failed" in entry.error


class TestDomainScheduling:
    """Test domain scheduling functions."""

    def test_submit_domain_setup_skips_if_future_exists(self, vis: MockViseron) -> None:
        """Test _submit_domain_setup skips if future already exists."""
        vis.domain_registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        future: Future[bool] = Future()
        vis.domain_registry.set_future("camera", "cam1", future)

        with ThreadPoolExecutor(max_workers=1) as executor:
            _submit_domain_setup(vis, executor, entry)
            assert vis.domain_registry.get_future("camera", "cam1") is future

    def test_submit_domain_setup_creates_future(self, vis: MockViseron) -> None:
        """Test _submit_domain_setup creates future when none exists."""
        mock_domain = MockDomainModule(setup_return=True)

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with (
            patch(
                "viseron.components.importlib.import_module", return_value=mock_domain
            ),
            ThreadPoolExecutor(max_workers=1) as executor,
        ):
            _submit_domain_setup(vis, executor, entry)
            # Wait for completion
            future = vis.domain_registry.get_future("camera", "cam1")
            assert future is not None
            future.result()

    def test_schedule_domain_setup_schedules_dependencies_first(
        self, vis: MockViseron
    ) -> None:
        """Test _schedule_domain_setup schedules required deps first."""
        mock_domain = MockDomainModule(setup_return=True)

        # Register dependency
        vis.domain_registry.register(
            component_name="dep_comp",
            component_path="dep.path",
            domain="object_detector",
            identifier="detector1",
            config={},
        )

        # Register main domain with dependency
        vis.domain_registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("object_detector", "detector1")],
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with (
            patch(
                "viseron.components.importlib.import_module", return_value=mock_domain
            ),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            _schedule_domain_setup(vis, executor, entry)

            cam_future = vis.domain_registry.get_future("camera", "cam1")
            det_future = vis.domain_registry.get_future("object_detector", "detector1")

            assert cam_future is not None
            assert det_future is not None

            det_future.result()
            cam_future.result()


class TestSetupDomains:
    """Test setup_domains function."""

    def test_setup_domains_validates_missing_dependencies(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test setup_domains validates and fails domains with missing deps."""
        vis.domain_registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
            require_domains=[
                RequireDomain(
                    "missing_domain",  # type: ignore[arg-type]
                    "missing_id",
                ),
            ],
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        setup_domains(vis)

        assert entry.state == DomainState.FAILED
        assert "has missing dependencies" in caplog.text

    def test_setup_domains_no_pending_returns_early(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test setup_domains returns early when no pending domains."""
        setup_domains(vis)
        assert "Setting up" not in caplog.text

    def test_setup_domains_clears_futures_after_completion(
        self, vis: MockViseron
    ) -> None:
        """Test setup_domains clears futures after all complete."""
        mock_domain = MockDomainModule(setup_return=True)

        vis.domain_registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        entry = vis.domain_registry.get("camera", "cam1")
        assert entry is not None

        with patch(
            "viseron.components.importlib.import_module", return_value=mock_domain
        ):
            setup_domains(vis)

            future = vis.domain_registry.get_future("camera", "cam1")
            assert future is None
            assert entry.state == DomainState.LOADED
