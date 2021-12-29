"""Home Assistant MQTT camera."""
from __future__ import annotations

from .entity import HassMQTTEntity

DOMAIN = "camera"


class HassMQTTCamera(HassMQTTEntity):
    """Base class for all Home Assistant MQTT cameras."""

    # These should NOT be overridden.
    domain = DOMAIN

    @property
    def config_payload(self):
        """Return config payload."""
        payload = super().config_payload
        del payload["state_topic"]
        del payload["value_template"]
        payload["topic"] = self.state_topic
        return payload
