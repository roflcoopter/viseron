"""Binary sensor for a camera."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.helpers.entity.binary_sensor import BinarySensorEntity

from ..const import (
    EVENT_CAMERA_STATUS,
    EVENT_CAMERA_STILL_IMAGE_AVAILABLE,
    EVENT_RECORDER_START,
    EVENT_RECORDER_STOP,
)
from . import CameraEntity

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import (
        EventCameraStatusData,
        EventCameraStillImageAvailable,
    )
    from viseron.domains.camera.recorder import EventRecorderData, Recording

    from .. import AbstractCamera


class CameraBinarySensor(CameraEntity, BinarySensorEntity):
    """Base class for a binary sensor that is tied to a specific AbstractCamera."""


class ConnectionStatusBinarySensor(CameraBinarySensor):
    """Entity that keeps track of connection to camera."""

    def __init__(self, vis: Viseron, camera: AbstractCamera) -> None:
        super().__init__(vis, camera)
        self.device_class = "connectivity"
        self.entity_category = "diagnostic"
        self.object_id = f"{camera.identifier}_connected"
        self.name = f"{camera.name} Connected"

    def setup(self) -> None:
        """Set up event listener."""
        self._vis.listen_event(
            EVENT_CAMERA_STATUS.format(camera_identifier=self._camera.identifier),
            self.handle_event,
        )

    @property
    def _is_on(self):
        return self._camera.connected

    def handle_event(self, _event_data: Event[EventCameraStatusData]) -> None:
        """Handle status event."""
        self.set_state()


class RecorderBinarySensor(CameraBinarySensor):
    """Entity that keeps track of the recorder of a camera."""

    def __init__(self, vis: Viseron, camera: AbstractCamera) -> None:
        super().__init__(vis, camera)
        self.device_class = "running"
        self.object_id = f"{camera.identifier}_recorder"
        self.name = f"{camera.name} Recorder"

        self._recording: Recording | None = None

    def setup(self) -> None:
        """Set up event listener."""
        self._vis.listen_event(
            EVENT_RECORDER_START.format(camera_identifier=self._camera.identifier),
            self.handle_start_event,
        )
        self._vis.listen_event(
            EVENT_RECORDER_STOP.format(camera_identifier=self._camera.identifier),
            self.handle_stop_event,
        )

    @property
    def extra_attributes(self):
        """Return extra attributes."""
        if self._recording:
            return self._recording.as_dict()
        return {}

    def handle_start_event(self, event_data: Event[EventRecorderData]) -> None:
        """Handle recorder start event."""
        self._recording = event_data.data.recording
        self._is_on = True
        self.set_state()

    def handle_stop_event(self, event_data: Event[EventRecorderData]) -> None:
        """Handle recorder stop event."""
        self._recording = event_data.data.recording
        self._is_on = False
        self.set_state()


class StillImageAvailableBinarySensor(CameraBinarySensor):
    """Entity that keeps track of the still image availability of a camera."""

    def __init__(self, vis: Viseron, camera: AbstractCamera) -> None:
        super().__init__(vis, camera)
        self.device_class = None
        self.object_id = f"{camera.identifier}_still_image_available"
        self.name = f"{camera.name} Still Image Available"

    def setup(self) -> None:
        """Set up event listener."""
        self._vis.listen_event(
            EVENT_CAMERA_STILL_IMAGE_AVAILABLE.format(
                camera_identifier=self._camera.identifier
            ),
            self.handle_event,
        )

    @property
    def _is_on(self):
        return self._camera.still_image_available

    def handle_event(self, _event_data: Event[EventCameraStillImageAvailable]) -> None:
        """Handle still image available event."""
        self.set_state()
