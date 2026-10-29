"""Tests for the states registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from viseron.helpers.entity import Entity

from tests.common import MockComponent

if TYPE_CHECKING:
    from viseron.viseron_types import SupportedDomains

    from tests.conftest import MockViseron


class MockEntity(Entity):
    """Entity used to exercise the registry."""

    domain = "binary_sensor"

    def __init__(self, vis: MockViseron, name: str) -> None:
        super().__init__(vis)
        self.name = name


class TestGetEntityIdentifier:
    """Tests for States.get_entity_identifier."""

    @staticmethod
    def _add(
        vis: MockViseron,
        name: str,
        domain: SupportedDomains | None = None,
        identifier: str | None = None,
    ) -> Entity:
        """Add an entity to the registry."""
        component = MockComponent(vis, "test_comp")
        if domain is not None and identifier is not None:
            return vis.states.add_entity(
                component, MockEntity(vis, name), domain, identifier
            )
        return vis.states.add_entity(component, MockEntity(vis, name))

    def test_returns_the_identifier_the_entity_was_registered_under(
        self, vis: MockViseron
    ) -> None:
        """The registration identifier is what ties an entity to a camera."""
        entity = self._add(vis, "cam_a face", "face_recognition", "cam_a")

        assert vis.states.get_entity_identifier(entity.entity_id) == "cam_a"

    def test_returns_none_for_an_entity_registered_without_identifier(
        self, vis: MockViseron
    ) -> None:
        """Entities not scoped to a domain identifier have no owner."""
        entity = self._add(vis, "cpu load")

        assert vis.states.get_entity_identifier(entity.entity_id) is None

    def test_returns_none_for_an_unknown_entity(self, vis: MockViseron) -> None:
        """Unregistered entity ids resolve to no owner."""
        assert vis.states.get_entity_identifier("binary_sensor.nonexistent") is None

    def test_returns_none_once_the_entity_is_unloaded(self, vis: MockViseron) -> None:
        """Unloading an entity forgets its owner."""
        entity = self._add(vis, "cam_a face", "face_recognition", "cam_a")

        vis.states.unload_entity(entity.entity_id)

        assert vis.states.get_entity_identifier(entity.entity_id) is None


class TestUnloadEntity:
    """Tests for States.unload_entity."""

    def test_removes_entity_from_the_owner_registry(self, vis: MockViseron) -> None:
        """The owner registry must not keep unloaded entities around."""
        component = MockComponent(vis, "test_comp")
        entity = vis.states.add_entity(
            component,
            MockEntity(vis, "cam_a face"),
            "face_recognition",
            "cam_a",
        )

        vis.states.unload_entity(entity.entity_id)

        identifiers = vis.states.entity_owner["test_comp"]["domains"][
            "face_recognition"
        ]["identifiers"]
        assert identifiers["cam_a"] == []

    def test_removes_undomained_entity_from_the_owner_registry(
        self, vis: MockViseron
    ) -> None:
        """Entities registered without a domain are removed as well."""
        component = MockComponent(vis, "test_comp")
        entity = vis.states.add_entity(component, MockEntity(vis, "cpu load"))

        vis.states.unload_entity(entity.entity_id)

        assert vis.states.entity_owner["test_comp"]["entities"] == []


class TestAddEntityOwnership:
    """Tests for the domain/identifier pairing in States.add_entity."""

    def test_rejects_a_domain_without_an_identifier(self, vis: MockViseron) -> None:
        """A domain without an identifier would be unowned and unloadable."""
        component = MockComponent(vis, "test_comp")

        with pytest.raises(ValueError, match="domain and identifier"):
            vis.states.add_entity(
                component,
                MockEntity(vis, "cam_a face"),
                "face_recognition",  # type: ignore[call-overload]
            )

    def test_rejects_an_identifier_without_a_domain(self, vis: MockViseron) -> None:
        """An identifier without a domain has nothing to scope it to."""
        component = MockComponent(vis, "test_comp")

        with pytest.raises(ValueError, match="domain and identifier"):
            vis.states.add_entity(
                component,
                MockEntity(vis, "cam_a face"),
                identifier="cam_a",  # type: ignore[call-overload]
            )

    def test_rejected_entity_is_not_registered(self, vis: MockViseron) -> None:
        """The registry must not be left holding a half-registered entity."""
        component = MockComponent(vis, "test_comp")

        with pytest.raises(ValueError):
            vis.states.add_entity(
                component,
                MockEntity(vis, "cam_a face"),
                "face_recognition",  # type: ignore[call-overload]
            )

        assert vis.states.get_entities() == {}
