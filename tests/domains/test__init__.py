"""Tests for domains module."""
import logging
from concurrent.futures import Future
from logging import DEBUG
from unittest.mock import Mock, patch

import pytest

from viseron.domain_registry import DomainEntry, DomainState
from viseron.domains import (
    OptionalDomain,
    RequireDomain,
    _handle_failed_domain,
    _wait_for_dependencies,
    get_unload_order,
    reload_domain,
    unload_domain,
)

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
        "target_domain,target_id,expected_count",
        [
            ("camera", "cam1", 2),  # nvr depends on cam1
            ("camera", "cam2", 1),  # No dependents on cam2
            ("nvr", "cam1", 1),  # nvr itself, no dependents
        ],
    )
    def test_different_identifiers(
        self, vis: MockViseron, target_domain, target_id, expected_count
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


class TestUnloadDomain:
    """Test unload_domain function."""

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

        result = unload_domain(vis, "camera", "cam1")
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

        result = unload_domain(vis, "camera", "cam1")
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

        result = unload_domain(vis, "camera", "cam1")
        assert result is not None
        assert registry.get("camera", "cam1") is None
        mock_instance.unload.assert_called_once()

    def test_unload_removes_entities(self, vis: MockViseron):
        """Test that entities are removed during unload."""
        # Set up entity ownership structure
        vis.states._register_entity_owner(  # pylint: disable=protected-access
            "test_comp",
            "entity.test1",
            "camera",
            "cam1",
        )
        vis.states._register_entity_owner(  # pylint: disable=protected-access
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
            unload_domain(vis, "camera", "cam1")
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
        self, vis: MockViseron, entity_structure
    ):
        """Test unload handles missing or incomplete entity structures."""
        vis.states._entity_owner = entity_structure  # pylint: disable=protected-access

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
            result = unload_domain(vis, "camera", "cam1")
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

        result = unload_domain(vis, "camera", "cam1")
        assert result is not None
        assert registry.get("camera", "cam1") is None
        assert "Domain camera with identifier cam1 has no unload method" in caplog.text


class TestReloadDomain:
    """Test reload_domain function."""

    def test_reload_nonexistent_domain(
        self, vis: MockViseron, caplog: pytest.LogCaptureFixture
    ):
        """Test reload warns when domain doesn't exist."""
        reload_domain(vis, "camera", "cam1")

        assert "Domain camera with identifier cam1 not found for reload" in caplog.text

    def test_reload_single_domain_no_dependents(self, vis: MockViseron):
        """Test reloading a single domain with no dependents."""
        registry = vis.domain_registry
        registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={"test": "config"},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        with patch("viseron.domains.unload_domain") as mock_unload, patch(
            "viseron.domains.setup_domains"
        ) as mock_setup:
            reload_domain(vis, "camera", "cam1")

            mock_unload.assert_called_once_with(vis, "camera", "cam1")
            mock_setup.assert_called_once_with(vis)

    def test_reload_domain_with_dependents(self, vis: MockViseron):
        """Test reloading a domain with dependents."""
        registry = vis.domain_registry
        registry.register(
            component_name="camera_comp",
            component_path="camera.path",
            domain="camera",
            identifier="cam1",
            config={"camera": "config"},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        # Register dependent domain
        registry.register(
            component_name="nvr_comp",
            component_path="nvr.path",
            domain="nvr",
            identifier="cam1",
            config={"nvr": "config"},
            require_domains=[RequireDomain("camera", "cam1")],
        )
        registry.set_state("nvr", "cam1", DomainState.LOADED)

        with patch("viseron.domains.unload_domain") as mock_unload, patch(
            "viseron.domains.setup_domains"
        ) as mock_setup:
            reload_domain(vis, "camera", "cam1")

            calls = [call[0] for call in mock_unload.call_args_list]
            assert calls[0] == (vis, "nvr", "cam1")
            assert calls[1] == (vis, "camera", "cam1")

            mock_setup.assert_called_once_with(vis)

    def test_reload_domain_optional_dependents(self, vis: MockViseron):
        """Test reloading a domain with optional dependents."""
        registry = vis.domain_registry
        registry.register(
            component_name="camera_comp",
            component_path="camera.path",
            domain="camera",
            identifier="cam1",
            config={"setting": "value"},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)
        registry.register(
            component_name="motion_comp",
            component_path="motion.path",
            domain="motion_detector",
            identifier="cam1",
            config={"motion_setting": "motion_value"},
            require_domains=[RequireDomain("camera", "cam1")],
        )
        registry.set_state("motion_detector", "cam1", DomainState.LOADED)

        require_deps = [RequireDomain("camera", "cam1")]
        optional_deps = [OptionalDomain("motion_detector", "cam1")]
        registry.register(
            component_name="nvr_comp",
            component_path="nvr.path",
            domain="nvr",
            identifier="cam1",
            config={"nvr_setting": "nvr_value"},
            require_domains=require_deps,
            optional_domains=optional_deps,
        )
        registry.set_state("nvr", "cam1", DomainState.LOADED)

        with patch("viseron.domains.unload_domain") as mock_unload, patch(
            "viseron.domains.setup_domains"
        ):
            reload_domain(vis, "camera", "cam1")

            calls = [call[0] for call in mock_unload.call_args_list]
            assert calls[0] == (vis, "nvr", "cam1")
            assert calls[1] == (vis, "motion_detector", "cam1")
            assert calls[2] == (vis, "camera", "cam1")

            # Should re-register all three
            assert registry.get("camera", "cam1") is not None
            assert registry.get("motion_detector", "cam1") is not None
            assert registry.get("nvr", "cam1") is not None


class TestHandleFailedDomain:
    """Test _handle_failed_domain function."""

    @pytest.mark.parametrize(
        "state",
        [DomainState.FAILED, DomainState.RETRYING],
    )
    def test_handle_failed_domain_sets_state(self, vis: MockViseron, state) -> None:
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

        def setup_failed_handler(_vis_arg, _entry_arg) -> Mock:
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
