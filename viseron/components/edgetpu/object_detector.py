"""EdgeTPU Object detector."""
import logging
import threading
from queue import Queue

import cv2
import numpy as np

from viseron import Viseron
from viseron.domains.object_detector import AbstractObjectDetector
from viseron.domains.object_detector.const import DOMAIN
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.exceptions import DomainNotReady

from . import EdgeTPUDetection, MakeInterpreterError
from .const import COMPONENT, CONFIG_OBJECT_DETECTOR

LOGGER = logging.getLogger(__name__)

MAKE_INTERPRETER_LOCK = threading.Lock()


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the edgetpu object_detector domain."""
    with MAKE_INTERPRETER_LOCK:
        if not vis.data[COMPONENT].get(CONFIG_OBJECT_DETECTOR, None):
            try:
                vis.data[COMPONENT][CONFIG_OBJECT_DETECTOR] = EdgeTPUDetection(
                    vis, config[CONFIG_OBJECT_DETECTOR], CONFIG_OBJECT_DETECTOR
                )
            except (MakeInterpreterError, FileNotFoundError) as error:
                raise DomainNotReady from error

    ObjectDetector(vis, config[DOMAIN], identifier)

    return True


class ObjectDetector(AbstractObjectDetector):
    """Performs object detection."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        self._vis = vis
        self._config = config
        self._camera_identifier = camera_identifier

        self._edgetpu: EdgeTPUDetection = vis.data[COMPONENT][CONFIG_OBJECT_DETECTOR]
        self._object_result_queue: Queue[list[DetectedObject]] = Queue(maxsize=1)

        super().__init__(vis, COMPONENT, config, camera_identifier)

        vis.register_domain(DOMAIN, camera_identifier, self)

    def preprocess(self, frame):
        """Return preprocessed frame before performing object detection."""
        frame = cv2.resize(
            frame,
            (self.model_width, self.model_height),
            interpolation=cv2.INTER_LINEAR,
        )
        return np.expand_dims(frame, axis=0)

    def return_objects(self, frame) -> list[DetectedObject]:
        """Perform object detection."""
        return self._edgetpu.invoke(
            frame,
            self._camera_identifier,
            self._object_result_queue,
            self._camera.resolution,
        )

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._edgetpu.model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._edgetpu.model_height
