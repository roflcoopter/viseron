"""Base binary sensor entity class."""
from __future__ import annotations

from viseron.const import STATE_OFF, STATE_ON
from viseron.helpers.entity import Entity

ENTITY_ID_FORMAT = "binary_sensor.{name}"


class BinarySensorEntity(Entity):
    """Base binary sensor entity class."""

    entity_id_format = ENTITY_ID_FORMAT

    _is_on: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return STATE_ON if self.is_on else STATE_OFF
