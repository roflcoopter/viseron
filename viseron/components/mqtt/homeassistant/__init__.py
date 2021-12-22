"""Home Assistant MQTT integration."""
from __future__ import annotations

import logging
import threading
from typing import Dict, List

from viseron import EventData, EventEntityAddedData, Viseron
from viseron.const import EVENT_ENTITY_ADDED
from viseron.helpers.entity import Entity

from .binary_sensor import HassMQTTBinarySensor
from .entity import HassMQTTEntity

LOGGER = logging.getLogger(__name__)

DOMAIN_MAP = {
    "binary_sensor": HassMQTTBinarySensor,
}


class HassMQTTInterface:
    """MQTT interface to Home Assistant."""

    def __init__(self, vis: Viseron, config):
        self._vis = vis
        self._config = config

        self._entity_creation_lock = threading.Lock()
        self._entities: Dict[str, HassMQTTEntity] = {}
        vis.listen_event(EVENT_ENTITY_ADDED, self.entity_added)
        self.create_entities(vis.get_entities())

    def create_entity(self, entity):
        """Create entity in Home Assistant."""
        with self._entity_creation_lock:
            if entity.entity_id in self._entities:
                LOGGER.debug(f"Entity {entity.entity_id} has already been added")
                return

            domain = entity.entity_id.split(".")[0]
            if entity_class := DOMAIN_MAP.get(domain):
                mqtt_entity = entity_class(self._vis, self._config, entity)
            else:
                LOGGER.debug(f"Unsupported domain encountered: {domain}")
                return

            mqtt_entity.create()
            self._entities[entity.entity_id] = mqtt_entity

    def create_entities(self, entities: List[Entity]):
        """Create entities in Home Assistant."""
        for entity in entities:
            self.create_entity(entity)

    def entity_added(self, event_data: EventData):
        """Add entity to Home Assistant when its added to Viseron."""
        entity_added_data: EventEntityAddedData = event_data.data
        self.create_entity(entity_added_data.entity)
