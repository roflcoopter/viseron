"""Binary sensor that represents motion detection."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.domains.camera.entity.binary_sensor import CameraBinarySensor

from .const import EVENT_FACE_DETECTED, EVENT_FACE_EXPIRED

if TYPE_CHECKING:
    from viseron import EventData, Viseron
    from viseron.domains.camera import AbstractCamera


class FaceDetectionBinarySensor(CameraBinarySensor):
    """Entity that keeps track of face detection."""

    def __init__(self, vis: Viseron, camera: AbstractCamera, face: str):
        super().__init__(vis, camera)
        self.object_id = f"{camera.identifier}_face_detected_{face}"
        self.name = f"{camera.name} Face Detected {face.capitalize()}"

        self._detected = False

        vis.listen_event(
            EVENT_FACE_DETECTED.format(camera_identifier=camera.identifier, face=face),
            self.face_detected,
        )
        vis.listen_event(
            EVENT_FACE_EXPIRED.format(camera_identifier=camera.identifier, face=face),
            self.face_expired,
        )

    @property
    def _is_on(self):
        return self._detected

    def face_detected(self, _event_data: EventData):
        """Handle face detected event."""
        self._detected = True
        self.set_state()

    def face_expired(self, _event_data: EventData):
        """Handle face expired event."""
        self._detected = False
        self.set_state()
