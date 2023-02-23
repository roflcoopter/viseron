"""Sensor entity for a camera."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.helpers.entity.sensor import SensorEntity

from . import CameraEntity

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.camera import AbstractCamera


class CameraSensor(CameraEntity, SensorEntity):
    """Base class for a sensor that is tied to a specific AbstractCamera."""


class CamerAccessTokenSensor(CameraSensor):
    """Entity that holds the value of the current access token for a camera."""

    def __init__(
        self,
        vis: Viseron,
        camera: AbstractCamera,
    ):
        super().__init__(vis, camera)

        self.entity_category = "diagnostic"
        self.object_id = f"{camera.identifier}_access_token"
        self.name = f"{camera.name} Access Token"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._camera.access_token
