"""Hailo object detector."""

from __future__ import annotations

import logging
import threading
from queue import Queue
from typing import TYPE_CHECKING, Any

from viseron.domains.object_detector import AbstractObjectDetector
from viseron.exceptions import DomainNotReady

from . import Hailo8Detector
from .const import COMPONENT, CONFIG_OBJECT_DETECTOR

if TYPE_CHECKING:
    import numpy as np

    from viseron import Viseron
    from viseron.domains.object_detector.detected_object import DetectedObject


LOGGER = logging.getLogger(__name__)

SETUP_LOCK = threading.Lock()


def setup(vis: Viseron, config: dict[str, Any], identifier: str) -> bool:
    """Set up the Hailo object_detector domain."""
    with SETUP_LOCK:
        if not vis.data[COMPONENT].get(CONFIG_OBJECT_DETECTOR, None):
            try:
                vis.data[COMPONENT][CONFIG_OBJECT_DETECTOR] = Hailo8Detector(
                    vis, config
                )
            except Exception as error:
                raise DomainNotReady from error
        else:
            LOGGER.debug("Hailo detector has already been created")

    ObjectDetector(vis, config, identifier)

    return True


def unload(vis: Viseron) -> None:
    """Unload the Hailo object_detector domain."""
    if detector := vis.data.get(COMPONENT, {}).get(CONFIG_OBJECT_DETECTOR, None):
        detector.stop()
        vis.data[COMPONENT].pop(CONFIG_OBJECT_DETECTOR, None)


class ObjectDetector(AbstractObjectDetector):
    """Hailo object detection."""

    def __init__(
        self, vis: Viseron, config: dict[str, Any], camera_identifier: str
    ) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_OBJECT_DETECTOR], camera_identifier
        )
        self._hailo8 = vis.data[COMPONENT][CONFIG_OBJECT_DETECTOR]
        self._object_result_queue: Queue[list[DetectedObject]] = Queue(maxsize=1)

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame before detection."""
        return self._hailo8.preprocess(frame)

    def return_objects(self, frame: np.ndarray) -> list[DetectedObject] | None:
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
