"""Binary sensor that represents motion detection."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.domains.camera.entity.binary_sensor import CameraBinarySensor

from .const import EVENT_MOTION_DETECTED

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.motion_detector import EventMotionDetected

    from . import AbstractMotionDetector


class MotionDetectionBinarySensor(CameraBinarySensor):
    """Entity that keeps track of motion detection."""

    def __init__(
        self,
        vis: Viseron,
        motion_detector: AbstractMotionDetector,
        camera: AbstractCamera,
    ):
        super().__init__(vis, camera)
        self._motion_detector = motion_detector
        self.device_class = "motion"
        self.object_id = f"{camera.identifier}_motion_detected"
        self.name = f"{camera.name} Motion Detected"

        vis.listen_event(
            EVENT_MOTION_DETECTED.format(camera_identifier=camera.identifier),
            self.handle_event,
        )

    @property
    def _is_on(self):
        return self._motion_detector.motion_detected

    def handle_event(self, _event_data: Event[EventMotionDetected]):
        """Handle status event."""
        self.set_state()
