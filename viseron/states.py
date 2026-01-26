"""Viseron states registry."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from viseron.const import EVENT_ENTITY_ADDED, EVENT_STATE_CHANGED
from viseron.events import EventData
from viseron.helpers import slugify
from viseron.helpers.logs import development_warning
from viseron.types import SupportedDomains

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components import Component
    from viseron.helpers.entity import Entity

LOGGER = logging.getLogger(__name__)


@dataclass
class EventStateChangedData(EventData):
    """State changed event data."""

    entity_id: str
    previous_state: State | None
    current_state: State

    _as_dict: dict[str, Any] | None = None

    def as_dict(self):
        """Return state changed event as dict."""
        if not self._as_dict:
            self._as_dict = {
                "entity_id": self.entity_id,
                "previous_state": self.previous_state,
                "current_state": self.current_state,
            }
        return self._as_dict


@dataclass
class EventEntityAddedData(EventData):
    """Entity event data."""

    entity: Entity


class DomainOwnerDict(TypedDict):
    """Domain owner structure."""

    identifiers: dict[str, list[str]]


class ComponentOwnerDict(TypedDict):
    """Component owner structure."""

    entities: list[str]
    domains: dict[SupportedDomains, DomainOwnerDict]


EntityOwner = dict[str, ComponentOwnerDict]


class State:
    """Hold the state of a single entity."""

    def __init__(
        self,
        entity_id: str,
        state: str,
        attributes: dict,
    ) -> None:
        self.entity_id = entity_id
        self.state = state
        self.attributes = attributes
        self.timestamp = time.time()

        self._as_dict: dict[str, Any] | None = None

    def as_dict(self):
        """Return state as dict."""
        if not self._as_dict:
            self._as_dict = {
                "entity_id": self.entity_id,
                "state": self.state,
                "attributes": self.attributes,
                "timestamp": self.timestamp,
            }
        return self._as_dict


class States:
    """Keep track of entity states."""

    def __init__(self, vis: Viseron) -> None:
        self._vis = vis
        self._registry: dict[str, Entity] = {}
        self._registry_lock = threading.Lock()
        self._entity_owner: EntityOwner = {}

        self._current_states: dict[str, State] = {}

    @property
    def current(self) -> dict[str, State]:
        """Return current states."""
        return self._current_states

    @property
    def entity_owner(self) -> EntityOwner:
        """Return entity owner registry."""
        return self._entity_owner

    def set_state(self, entity: Entity) -> None:
        """Set the state in the states registry."""
        LOGGER.debug(
            "Setting state of %s to state: %s, attributes %s",
            entity.entity_id,
            entity.state,
            entity.attributes,
        )

        previous_state = self._current_states.get(entity.entity_id, None)
        current_state = State(
            entity.entity_id,
            entity.state,
            entity.attributes,
        )

        self._current_states[entity.entity_id] = current_state
        self._vis.dispatch_event(
            EVENT_STATE_CHANGED,
            EventStateChangedData(
                entity_id=entity.entity_id,
                previous_state=previous_state,
                current_state=current_state,
            ),
        )

    def add_entity(
        self,
        component: Component,
        entity: Entity,
        domain: SupportedDomains | None = None,
        identifier: str | None = None,
    ) -> Entity | None:
        """Add entity to states registry."""
        with self._registry_lock:
            if not entity.name:
                LOGGER.error(
                    f"Component {component.name} is adding entities without name. "
                    "name is required for all entities"
                )
                return None

            LOGGER.debug(f"Adding entity {entity.name} from component {component.name}")

            if entity.entity_id:
                entity_id = entity.entity_id
            else:
                entity_id = self._generate_entity_id(entity)

            if entity_id in self._registry:
                LOGGER.error(
                    f"Component {component.name} does not generate unique entity IDs"
                )
                suffix_number = 1
                while True:
                    if (
                        unique_entity_id := f"{entity_id}_{suffix_number}"
                    ) in self._registry:
                        suffix_number += 1
                    else:
                        entity_id = unique_entity_id
                        break

            entity.entity_id = entity_id
            entity.vis = self._vis

            self._registry[entity_id] = entity
            if hasattr(entity, "setup"):
                entity.setup()

                if not hasattr(entity, "unload"):
                    development_warning(
                        LOGGER,
                        f"Entity {entity.entity_id} from component {component.name} "
                        "is missing unload method",
                    )

            self._register_entity_owner(
                component.name, entity.entity_id, domain, identifier
            )

            self._vis.dispatch_event(
                EVENT_ENTITY_ADDED, EventEntityAddedData(entity), store=False
            )
            self.set_state(entity)
            return entity

    def _register_entity_owner(
        self,
        component_name: str,
        entity_id: str,
        domain: SupportedDomains | None = None,
        identifier: str | None = None,
    ) -> None:
        """Register entity ownership for tracking."""
        self._ensure_component_owner_entry(component_name)

        if domain:
            self._register_domain_entity(component_name, domain, identifier, entity_id)
        else:
            self._entity_owner[component_name]["entities"].append(entity_id)

    def _ensure_component_owner_entry(self, component_name: str) -> None:
        """Ensure component has an entry in entity owner registry."""
        if component_name not in self._entity_owner:
            self._entity_owner[component_name] = {
                "entities": [],
                "domains": {},
            }

    def _register_domain_entity(
        self,
        component_name: str,
        domain: SupportedDomains,
        identifier: str | None,
        entity_id: str,
    ) -> None:
        """Register entity under a specific domain."""
        domains = self._entity_owner[component_name]["domains"]

        if domain not in domains:
            domains[domain] = {"identifiers": {}}

        if identifier:
            if identifier not in domains[domain]["identifiers"]:
                domains[domain]["identifiers"][identifier] = []
            domains[domain]["identifiers"][identifier].append(entity_id)

    def get_entities(self):
        """Return all registered entities."""
        with self._registry_lock:
            return dict(sorted(self._registry.items()))

    def unload_entity(self, entity_id: str) -> None:
        """Unload entity from states registry."""
        with self._registry_lock:
            entity = self._registry.get(entity_id, None)
            if not entity:
                LOGGER.warning(f"Tried to unload non existing entity {entity_id}")
                return

            LOGGER.debug(f"Unloading entity {entity_id}")

            if hasattr(entity, "unload"):
                try:
                    entity.unload()
                    LOGGER.debug(f"Unloaded entity {entity_id}")
                except Exception as ex:  # pylint: disable=broad-except
                    LOGGER.error(f"Error unloading entity {entity_id}: {ex}")
            else:
                development_warning(LOGGER, f"Entity {entity_id} has no unload method")

            del self._registry[entity_id]
            if entity_id in self._current_states:
                del self._current_states[entity_id]

    @staticmethod
    def _assign_object_id(entity: Entity) -> None:
        """Assign object id to entity if it is missing."""
        if entity.object_id:
            entity.object_id = slugify(entity.object_id)
        else:
            entity.object_id = slugify(entity.name)

    def entity_exists(self, entity: Entity) -> bool:
        """Return if entity has already been added."""
        return self._generate_entity_id(entity) in self._registry

    def _generate_entity_id(self, entity: Entity) -> str:
        """Generate entity id for an entity."""
        self._assign_object_id(entity)
        return f"{entity.domain}.{entity.object_id}"
