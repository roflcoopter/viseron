"""Home Assistant MQTT binary sensor."""
from __future__ import annotations

from typing import Final

from viseron.components.mqtt.entity.binary_sensor import BinarySensorMQTTEntity
from viseron.const import STATE_OFF, STATE_ON

from .entity import HassMQTTEntity

DOMAIN: Final = "binary_sensor"


class HassMQTTBinarySensor(HassMQTTEntity[BinarySensorMQTTEntity]):
    """Base class for all Home Assistant MQTT binary sensors."""

    # These should NOT be overridden.
    domain = DOMAIN

    @property
    def config_payload(self):
        """Return config payload."""
        payload = super().config_payload
        payload["payload_on"] = STATE_ON
        payload["payload_off"] = STATE_OFF

        if self._mqtt_entity.entity.device_class:
            payload["device_class"] = self._mqtt_entity.entity.device_class
        return payload
