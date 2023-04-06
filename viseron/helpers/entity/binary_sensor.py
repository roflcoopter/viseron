"""Base binary sensor entity class."""
from __future__ import annotations

from typing import Final

from viseron.const import STATE_OFF, STATE_ON
from viseron.helpers.entity import Entity

DOMAIN: Final = "binary_sensor"


class BinarySensorEntity(Entity):
    """Base binary sensor entity class."""

    # The following variables should NOT be overridden
    domain = DOMAIN

    # These are safe to override
    _is_on: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return STATE_ON if self.is_on else STATE_OFF
