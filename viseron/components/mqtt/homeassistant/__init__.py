"""Home Assistant MQTT integration."""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from viseron.components.mqtt.const import COMPONENT, EVENT_MQTT_ENTITY_ADDED
from viseron.components.mqtt.event import EventMQTTEntityAddedData

from .binary_sensor import HassMQTTBinarySensor
from .camera import HassMQTTCamera
from .entity import HassMQTTEntity
from .sensor import HassMQTTSensor
from .switch import HassMQTTSwitch

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.components.mqtt.entity import MQTTEntity

LOGGER = logging.getLogger(__name__)

DOMAIN_MAP = {
    "binary_sensor": HassMQTTBinarySensor,
    "image": HassMQTTCamera,
    "sensor": HassMQTTSensor,
    "toggle": HassMQTTSwitch,
}


class HassMQTTInterface:
    """MQTT interface to Home Assistant."""

    def __init__(self, vis: Viseron, config):
        self._vis = vis
        self._config = config

        self._mqtt = vis.data[COMPONENT]

        self._entity_creation_lock = threading.Lock()
        self._entities: dict[str, HassMQTTEntity] = {}
        vis.listen_event(EVENT_MQTT_ENTITY_ADDED, self.entity_added)
        self.create_entities(self._mqtt.get_entities())

    def create_entity(self, mqtt_entity: MQTTEntity):
        """Create entity in Home Assistant."""
        with self._entity_creation_lock:
            if mqtt_entity.entity.entity_id in self._entities:
                LOGGER.debug(
                    f"Entity {mqtt_entity.entity.entity_id} has already been added"
                )
                return

            if entity_class := DOMAIN_MAP.get(mqtt_entity.entity.domain):
                hass_entity: HassMQTTEntity = entity_class(
                    self._vis, self._config, mqtt_entity
                )
            else:
                LOGGER.debug(
                    f"Unsupported domain encountered: {mqtt_entity.entity.domain}"
                )
                return

            hass_entity.create()
            self._entities[mqtt_entity.entity.entity_id] = hass_entity

    def create_entities(self, entities):
        """Create entities in Home Assistant."""
        for entity in entities.values():
            self.create_entity(entity)

    def entity_added(self, event_data: Event):
        """Add entity to Home Assistant when its added to Viseron."""
        entity_added_data: EventMQTTEntityAddedData = event_data.data
        self.create_entity(entity_added_data.mqtt_entity)
