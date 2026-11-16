"""Tests for viseron.domain_registry."""

from unittest.mock import MagicMock

from viseron.domain_registry import DomainRegistry, DomainState


def _registry_with_entries() -> tuple[DomainRegistry, object, object]:
    """Return a registry with one retrying and one pending entry."""
    registry = DomainRegistry(MagicMock())
    retrying = registry.register(
        component_name="darknet",
        component_path="viseron.components.darknet",
        domain="object_detector",
        identifier="cam1",
        config={},
    )
    pending = registry.register(
        component_name="darknet",
        component_path="viseron.components.darknet",
        domain="object_detector",
        identifier="cam2",
        config={},
    )
    retrying.state = DomainState.RETRYING
    return registry, retrying, pending


class TestCancelAllRetries:
    """Tests for cancel_all_retries."""

    def test_returns_only_retrying_entries(self):
        """Test that only entries in the RETRYING state are returned."""
        registry, retrying, _pending = _registry_with_entries()
        assert registry.cancel_all_retries() == [retrying]

    def test_does_not_cancel_non_retrying_entries(self):
        """Test that the cancel event is only set for retrying entries.

        The event used to be set for every registered entry, so a pending
        domain whose setup hit DomainNotReady right after a config reload was
        marked failed permanently instead of entering its retry loop.
        """
        registry, retrying, pending = _registry_with_entries()
        registry.cancel_all_retries()
        assert retrying.cancel_event.is_set()
        assert not pending.cancel_event.is_set()
