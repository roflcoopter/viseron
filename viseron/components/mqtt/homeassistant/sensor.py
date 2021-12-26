"""Home Assistant MQTT sensor."""
from __future__ import annotations

from .entity import HassMQTTEntity

DOMAIN = "sensor"


class HassMQTTSensor(HassMQTTEntity):
    """Base class for all Home Assistant MQTT sensors."""

    # These should NOT be overridden.
    domain = DOMAIN

    @property
    def config_payload(self):
        """Return config payload."""
        payload = super().config_payload
        if self._entity.device_class:
            payload["device_class"] = self._entity.device_class
        return payload
