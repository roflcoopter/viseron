"""Binary sensor that represents connection to camera."""
from __future__ import annotations

from viseron.helpers.entity.sensor import SensorEntity

from .entity import CameraEntity


class CameraSensor(CameraEntity, SensorEntity):
    """Base class for a sensor that is tied to a specific AbstractCamera."""
