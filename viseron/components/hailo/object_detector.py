"""Hailo object detector."""
from __future__ import annotations

import logging
from queue import Queue
from typing import TYPE_CHECKING

from viseron.domains.object_detector import AbstractObjectDetector

from .const import COMPONENT, CONFIG_OBJECT_DETECTOR

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.object_detector.detected_object import DetectedObject


LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the Hailo object_detector domain."""
    ObjectDetector(vis, config, identifier)

    return True


class ObjectDetector(AbstractObjectDetector):
    """Hailo object detection."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_OBJECT_DETECTOR], camera_identifier
        )
        self._hailo8 = vis.data[COMPONENT]
        self._object_result_queue: Queue[list[DetectedObject]] = Queue(maxsize=1)

    def preprocess(self, frame):
        """Preprocess frame before detection."""
        return self._hailo8.preprocess(frame)

    def return_objects(self, frame) -> list[DetectedObject] | None:
        """Perform object detection."""
        detections = self._hailo8.detect(
            frame,
            self._camera_identifier,
            self._object_result_queue,
        )
        if detections is None:
            return None
        return self._hailo8.post_process(
            detections, self._camera.resolution, self.min_confidence
        )
