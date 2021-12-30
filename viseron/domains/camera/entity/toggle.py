"""Toggle entity for a camera."""
from __future__ import annotations

from viseron.helpers.entity.toggle import ToggleEntity

from . import CameraEntity


class CameraToggle(CameraEntity, ToggleEntity):
    """Base class for a toggle entity that is tied to a specific AbstractCamera."""
