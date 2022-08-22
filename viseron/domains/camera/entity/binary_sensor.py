"""Binary sensor for a camera."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.helpers.entity.binary_sensor import BinarySensorEntity

from ..const import EVENT_RECORDER_START, EVENT_RECORDER_STOP, EVENT_STATUS
from . import CameraEntity

if TYPE_CHECKING:
    from viseron import Event, Viseron

    from .. import AbstractCamera


class CameraBinarySensor(CameraEntity, BinarySensorEntity):
    """Base class for a binary sensor that is tied to a specific AbstractCamera."""


class ConnectionStatusBinarySensor(CameraBinarySensor):
    """Entity that keeps track of connection to camera."""

    def __init__(self, vis: Viseron, camera: AbstractCamera):
        super().__init__(vis, camera)
        self.device_class = "connectivity"
        self.entity_category = "diagnostic"
        self.object_id = f"{camera.identifier}_connected"
        self.name = f"{camera.name} Connected"

    def setup(self):
        """Set up event listener."""
        self._vis.listen_event(
            EVENT_STATUS.format(camera_identifier=self._camera.identifier),
            self.handle_event,
        )

    @property
    def _is_on(self):
        return self._camera.connected

    def handle_event(self, _event_data: Event):
        """Handle status event."""
        self.set_state()


class RecorderBinarySensor(CameraBinarySensor):
    """Entity that keeps track of the recorder of a camera."""

    def __init__(self, vis: Viseron, camera: AbstractCamera):
        super().__init__(vis, camera)
        self.device_class = "running"
        self.object_id = f"{camera.identifier}_recorder"
        self.name = f"{camera.name} Recorder"

    def setup(self):
        """Set up event listener."""
        self._vis.listen_event(
            EVENT_RECORDER_START.format(camera_identifier=self._camera.identifier),
            self.handle_start_event,
        )
        self._vis.listen_event(
            EVENT_RECORDER_STOP.format(camera_identifier=self._camera.identifier),
            self.handle_stop_event,
        )

    def handle_start_event(self, event_data: Event):
        """Handle recorder start event."""
        attributes = {}
        attributes["last_recording_start"] = event_data.data.start_time.isoformat()
        attributes["last_recording_end"] = None
        attributes["path"] = event_data.data.path
        if event_data.data.thumbnail_path:
            attributes["thumbnail_path"] = event_data.data.thumbnail_path

        self._attributes = attributes
        self._is_on = True
        self.set_state()

    def handle_stop_event(self, event_data: Event):
        """Handle recorder stop event."""
        attributes = {}
        attributes["last_recording_start"] = event_data.data.start_time.isoformat()
        attributes["last_recording_end"] = event_data.data.end_time.isoformat()
        attributes["path"] = event_data.data.path
        if event_data.data.thumbnail_path:
            attributes["thumbnail_path"] = event_data.data.thumbnail_path

        self._attributes = attributes
        self._is_on = False
        self.set_state()
