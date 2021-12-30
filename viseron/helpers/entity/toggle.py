"""Base toggle entity class."""
from __future__ import annotations

from viseron.const import STATE_OFF, STATE_ON
from viseron.helpers.entity import Entity

DOMAIN = "toggle"


class ToggleEntity(Entity):
    """Base toggle entity class."""

    # The following variables should NOT be overridden
    domain = DOMAIN

    # These are safe to override
    _is_on: bool | None = None

    # Used by Home Assistant, safe to override
    device_class: str | None = None

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return STATE_ON if self.is_on else STATE_OFF

    def turn_on(self):
        """Turn on entity."""
        raise NotImplementedError()

    def turn_off(self):
        """Turn off entity."""
        raise NotImplementedError()

    def toggle(self):
        """Turn off entity."""
        if self.is_on:
            self.turn_off()
        else:
            self.turn_on()
