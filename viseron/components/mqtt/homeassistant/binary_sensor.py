"""Home Assistant MQTT binary sensor."""
from __future__ import annotations

from .entity import HassMQTTEntity

DOMAIN = "binary_sensor"


class HassMQTTBinarySensor(HassMQTTEntity):
    """Base class for all Home Assistant MQTT binary sensors."""

    # These should NOT be overridden.
    domain = DOMAIN

    # These are safe to override.
    device_class: str | None = None

    @property
    def config_payload(self):
        """Return config payload."""
        payload = super().config_payload
        if self.device_class:
            payload["device_class"] = self.device_class
        return payload
