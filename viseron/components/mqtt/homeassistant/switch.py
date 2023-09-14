"""Home Assistant MQTT switch."""
from __future__ import annotations

from typing import Final

from viseron.components.mqtt.entity.toggle import ToggleMQTTEntity
from viseron.const import STATE_OFF, STATE_ON

from .entity import HassMQTTEntity

DOMAIN: Final = "switch"


class HassMQTTSwitch(HassMQTTEntity[ToggleMQTTEntity]):
    """Base class for all Home Assistant MQTT switches."""

    # These should NOT be overridden.
    domain = DOMAIN

    @property
    def config_payload(self):
        """Return config payload."""
        payload = super().config_payload
        payload["payload_on"] = STATE_ON
        payload["payload_off"] = STATE_OFF

        payload["state_on"] = STATE_ON
        payload["state_off"] = STATE_OFF

        payload["command_topic"] = self._mqtt_entity.command_topic
        if self._mqtt_entity.entity.device_class:
            payload["device_class"] = self._mqtt_entity.entity.device_class
        return payload
