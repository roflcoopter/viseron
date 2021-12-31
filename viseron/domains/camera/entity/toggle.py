"""Toggle entity for a camera."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.domains.camera.const import (
    EVENT_CAMERA_START,
    EVENT_CAMERA_STARTED,
    EVENT_CAMERA_STOP,
    EVENT_CAMERA_STOPPED,
)
from viseron.helpers.entity.toggle import ToggleEntity

from . import CameraEntity

if TYPE_CHECKING:
    from viseron import EventData, Viseron
    from viseron.domains.camera import AbstractCamera


class CameraToggle(CameraEntity, ToggleEntity):
    """Base class for a toggle entity that is tied to a specific AbstractCamera."""


class CameraConnectionToggle(CameraToggle):
    """Entity that toggles camera connection on/off."""

    def __init__(self, vis: Viseron, camera: AbstractCamera):
        super().__init__(vis, camera)
        self.object_id = f"{camera.identifier}_connection"
        self.name = f"{camera.name} Connection"
        self.icon = "mdi:cctv"

        vis.listen_event(
            EVENT_CAMERA_START.format(camera_identifier=self._camera.identifier),
            self.handle_start_event,
        )
        vis.listen_event(
            EVENT_CAMERA_STOP.format(camera_identifier=self._camera.identifier),
            self.handle_stop_event,
        )
        vis.listen_event(
            EVENT_CAMERA_STARTED.format(camera_identifier=self._camera.identifier),
            self.handle_started_stopped_event,
        )
        vis.listen_event(
            EVENT_CAMERA_STOPPED.format(camera_identifier=self._camera.identifier),
            self.handle_started_stopped_event,
        )

    @property
    def _is_on(self):
        """Return if frame reader is active."""
        return self._camera.is_on

    def turn_on(self):
        """Turn on camera."""
        self._camera.start_camera()

    def turn_off(self):
        """Turn off camera."""
        self._camera.stop_camera()

    def handle_start_event(self, _event_data: EventData):
        """Handle camera start event."""
        self.turn_on()

    def handle_stop_event(self, _event_data: EventData):
        """Handle recorder stop event."""
        self.turn_off()

    def handle_started_stopped_event(self, _event_data: EventData):
        """Handle camera started/stopped event."""
        self.set_state()
