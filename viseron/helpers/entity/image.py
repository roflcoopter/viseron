"""Base image entity class."""
from __future__ import annotations

from typing import Final

from viseron.helpers.entity import Entity

DOMAIN: Final = "image"


class ImageEntity(Entity):
    """Base image entity class."""

    domain = DOMAIN

    _state = None
