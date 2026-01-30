"""Tests for domains module."""
from logging import DEBUG
from unittest.mock import Mock, patch

import pytest

from viseron.domain_registry import DomainState
from viseron.domains import (
    OptionalDomain,
    RequireDomain,
    get_unload_order,
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

    def test_domain_not_loaded_excluded(self, vis: MockViseron):
        """Test that domains not in LOADED state are excluded."""
        registry = vis.domain_registry

        # Register but don't load
        registry.register(
            component_name="test_comp",
            component_path="test.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        # Leave in PENDING state

        result = get_unload_order(vis, "camera", "cam1")

        assert len(result) == 0

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

    def test_dependent_not_loaded_excluded(self, vis: MockViseron):
        """Test that dependents not in LOADED state are excluded."""
        registry = vis.domain_registry

        # Register and load base domain
        registry.register(
            component_name="camera_comp",
            component_path="camera.path",
            domain="camera",
            identifier="cam1",
            config={},
        )
        registry.set_state("camera", "cam1", DomainState.LOADED)

        # Register dependent but leave in FAILED state
        registry.register(
            component_name="nvr_comp",
            component_path="nvr.path",
            domain="nvr",
            identifier="cam1",
            config={},
            require_domains=[RequireDomain("camera", "cam1")],
        )
        registry.set_state("nvr", "cam1", DomainState.FAILED)

        result = get_unload_order(vis, "camera", "cam1")

        # Only camera should be in the list
        assert len(result) == 1
        assert result[0].domain == "camera"

    def test_nonexistent_domain(self, vis: MockViseron):
        """Test unload order for a domain that doesn't exist."""
        result = get_unload_order(vis, "nonexistent", "id1")

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

    @pytest.mark.parametrize(
        "state,expected_result",
        [
            (DomainState.PENDING, None),
            (DomainState.FAILED, None),
            (None, None),  # Domain not registered
        ],
    )
    def test_unload_invalid_states(self, vis: MockViseron, state, expected_result):
        """Test unload fails for invalid states."""
        registry = vis.domain_registry
        if state is not None:
            # Register domain but don't set to LOADED
            registry.register(
                component_name="test_comp",
                component_path="test.path",
                domain="camera",
                identifier="cam1",
                config={},
            )
            if state != DomainState.PENDING:
                registry.set_state("camera", "cam1", state)

        result = unload_domain(vis, "camera", "cam1")
        assert result == expected_result

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
