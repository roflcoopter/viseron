"""Base toggle entity class."""
from __future__ import annotations

from viseron.helpers.entity import Entity

DOMAIN = "toggle"


class ToggleEntity(Entity):
    """Base toggle entity class."""

    # The following variables should NOT be overridden
    domain = DOMAIN

    # Used by Home Assistant, safe to override
    device_class: str | None = None
