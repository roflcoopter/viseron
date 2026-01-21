"""Viseron states registry."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from viseron.const import EVENT_ENTITY_ADDED, EVENT_STATE_CHANGED
from viseron.events import EventData
from viseron.helpers import slugify
from viseron.helpers.logs import development_warning

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

        self._current_states: dict[str, State] = {}

    @property
    def current(self) -> dict[str, State]:
        """Return current states."""
        return self._current_states

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

    def add_entity(self, component: Component, entity: Entity):
        """Add entity to states registry."""
        with self._registry_lock:
            if not entity.name:
                LOGGER.error(
                    f"Component {component.name} is adding entities without name. "
                    "name is required for all entities"
                )
                return

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

            self._vis.dispatch_event(
                EVENT_ENTITY_ADDED, EventEntityAddedData(entity), store=False
            )
            self.set_state(entity)
            return entity

    def get_entities(self):
        """Return all registered entities."""
        with self._registry_lock:
            return dict(sorted(self._registry.items()))

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
