"""Toggle entity for a camera."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.helpers.entity.toggle import ToggleEntity

from ..const import EVENT_CAMERA_START, EVENT_CAMERA_STOP
from . import CameraEntity

if TYPE_CHECKING:
    from viseron import Viseron

    from .. import AbstractCamera


class CameraToggle(CameraEntity, ToggleEntity):
    """Base class for a toggle entity that is tied to a specific AbstractCamera."""


class CameraConnectionToggle(CameraToggle):
    """Entity that toggles camera connection on/off."""

    def __init__(self, vis: Viseron, camera: AbstractCamera):
        super().__init__(vis, camera)
        self.object_id = f"{camera.identifier}_connection"
        self.name = f"{camera.name} Connection"

        vis.listen_event(
            EVENT_CAMERA_START.format(camera_identifier=self._camera.identifier),
            self.turn_on,
        )
        vis.listen_event(
            EVENT_CAMERA_STOP.format(camera_identifier=self._camera.identifier),
            self.turn_off,
        )

    @property
    def _is_on(self):
        """Return if frame reader is active."""
        return self._camera.is_on

    def turn_on(self):
        """Turn on camera."""
        self._camera.start_camera()
        self.set_state()

    def turn_off(self):
        """Turn off camera."""
        self._camera.stop_camera()
        self.set_state()
