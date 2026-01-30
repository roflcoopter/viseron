"""Tests for domains module."""
import pytest

from viseron.domain_registry import DomainState
from viseron.domains import OptionalDomain, RequireDomain, get_unload_order

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
