"""Base image entity class."""
from __future__ import annotations

from typing import Final

import numpy as np

from viseron.helpers.entity import Entity

DOMAIN: Final = "image"


class ImageEntity(Entity):
    """Base image entity class."""

    domain = DOMAIN

    _state = "unknown"
    _image: np.ndarray | None = None

    @property
    def image(self):
        """Return the current image."""
        return self._image
