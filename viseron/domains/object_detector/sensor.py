"""Object detector sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from viseron.domains.camera.entity.sensor import CameraSensor

if TYPE_CHECKING:
    from apscheduler.schedulers.base import Job

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
    ) -> None:
        super().__init__(vis, camera)
        self._object_detector = object_detector
        self.object_id = f"{camera.identifier}_object_detector_fps"
        self.name = f"{camera.name} Object Detector FPS"
        self.icon = "mdi:speedometer"
        self.entity_category = "diagnostic"

        self._update_job: Job | None = None

    def setup(self) -> None:
        """Set up state updates."""
        self._update_job = self._vis.schedule_periodic_update(self, UPDATE_INTERVAL)

    @property
    def extra_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        return {
            "preprocessor_fps": self._object_detector.preproc_fps,
            "inference_fps": self._object_detector.inference_fps,
            "theoretical_max_fps": self._object_detector.theoretical_max_fps,
        }

    @property
    def state(self) -> float:
        """Return entity state."""
        return self._object_detector.theoretical_max_fps

    def update(self) -> None:
        """Update FPS sensors."""
        self.set_state()

    def unload(self) -> None:
        """Unload entity."""
        try:
            if self._update_job:
                self._update_job.remove()
        except Exception:  # pylint: disable=broad-except # noqa: BLE001, S110
            pass
        super().unload()
