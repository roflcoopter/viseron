"""Sensor entity for a camera."""
from __future__ import annotations

from viseron.helpers.entity.sensor import SensorEntity

from . import CameraEntity


class CameraSensor(CameraEntity, SensorEntity):
    """Base class for a sensor that is tied to a specific AbstractCamera."""
