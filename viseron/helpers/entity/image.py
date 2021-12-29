"""Base image entity class."""
from __future__ import annotations

from viseron.helpers.entity import Entity

DOMAIN = "image"


class ImageEntity(Entity):
    """Base image entity class."""

    domain = DOMAIN

    _state = None
