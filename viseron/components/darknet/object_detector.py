"""Darknet object detector."""
from __future__ import annotations

import logging
from queue import Queue
from typing import TYPE_CHECKING, List

from viseron.domains.object_detector import AbstractObjectDetector
from viseron.domains.object_detector.const import DOMAIN

from .const import COMPONENT

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.darknet import BaseDarknet
    from viseron.domains.object_detector.detected_object import DetectedObject


LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config, identifier):
    """Set up the darknet object_detector domain."""
    ObjectDetector(vis, config[DOMAIN], identifier)

    return True


class ObjectDetector(AbstractObjectDetector):
    """Performs object detection."""

    def __init__(self, vis: Viseron, config, camera_identifier):
        super().__init__(vis, COMPONENT, config, camera_identifier)
        self._darknet: BaseDarknet = vis.data[COMPONENT]
        self._object_result_queue: Queue[List[DetectedObject]] = Queue(maxsize=1)

        vis.register_domain(DOMAIN, camera_identifier, self)

    def preprocess(self, frame):
        """Return preprocessed frame before performing object detection."""
        return self._darknet.preprocess(frame)

    def return_objects(self, frame) -> List[DetectedObject]:
        """Perform object detection."""
        detections = self._darknet.detect(
            frame,
            self._camera_identifier,
            self._object_result_queue,
            self.min_confidence,
        )
        return self._darknet.post_process(detections, self._camera.resolution)

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._darknet.model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._darknet.model_height

    @property
    def model_res(self):
        """Return trained model resolution."""
        return self._darknet.model_res
