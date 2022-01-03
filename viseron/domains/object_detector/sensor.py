"""Object detector sensors."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.domains.camera.entity.sensor import CameraSensor

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.camera import AbstractCamera

    from . import AbstractObjectDetector

UPDATE_INTERVAL = 30


class ObjectDetectorFPSSensor(CameraSensor):
    """Entity that keeps track of object detection FPS."""

    def __init__(
        self,
        vis: Viseron,
        object_detector: AbstractObjectDetector,
        camera: AbstractCamera,
    ):
        super().__init__(vis, camera)
        self._object_detector = object_detector
        self.object_id = f"{camera.identifier}_object_detector_fps"
        self.name = f"{camera.name} Object Detector FPS"
        self.icon = "mdi:speedometer"
        self.entity_category = "diagnostic"

        vis.schedule_periodic_update(self, UPDATE_INTERVAL)

    @property
    def attributes(self):
        """Return entity attributes."""
        return {
            "preprocessor_fps": self._object_detector.preproc_fps,
            "inference_fps": self._object_detector.inference_fps,
            "theoretical_max_fps": self._object_detector.theoretical_max_fps,
        }

    @property
    def state(self):
        """Return entity state."""
        return self._object_detector.theoretical_max_fps

    def update(self):
        """Update FPS sensors."""
        self.set_state()
