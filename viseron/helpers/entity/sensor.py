"""Base sensor entity class."""
from __future__ import annotations

from typing import Final

from viseron.helpers.entity import Entity

DOMAIN: Final = "sensor"


class SensorEntity(Entity):
    """Base sensor entity class."""

    # The following variables should NOT be overridden
    domain = DOMAIN

    # Used by Home Assistant, safe to override
    device_class: str | None = None
