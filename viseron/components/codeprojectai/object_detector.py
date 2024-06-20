"""CodeProject.AI object detector."""
import logging

import codeprojectai.core as cpai
import cv2

from viseron import Viseron
from viseron.domains.object_detector import AbstractObjectDetector
from viseron.domains.object_detector.const import DOMAIN
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.helpers import letterbox_resize

from .const import (
    COMPONENT,
    CONFIG_CUSTOM_MODEL,
    CONFIG_HOST,
    CONFIG_IMAGE_SIZE,
    CONFIG_OBJECT_DETECTOR,
    CONFIG_PORT,
    CONFIG_TIMEOUT,
)

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the codeprojectai object_detector domain."""
    ObjectDetector(vis, config, identifier)

    return True


class ObjectDetector(AbstractObjectDetector):
    """CodeProject.AI object detection."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_OBJECT_DETECTOR], camera_identifier
        )

        self._ds_config = config
        self._detector = cpai.CodeProjectAIObject(
            ip=config[CONFIG_HOST],
            port=config[CONFIG_PORT],
            timeout=config[CONFIG_TIMEOUT],
            min_confidence=self.min_confidence,
            custom_model=self._config[CONFIG_CUSTOM_MODEL],
        )

        self._image_resolution = (
            self._config[CONFIG_IMAGE_SIZE]
            if self._config[CONFIG_IMAGE_SIZE]
            else self._camera.resolution[0],
            self._config[CONFIG_IMAGE_SIZE]
            if self._config[CONFIG_IMAGE_SIZE]
            else self._camera.resolution[1],
        )

        vis.register_domain(DOMAIN, camera_identifier, self)

    def preprocess(self, frame):
        """Preprocess frame before detection."""
        if self._config[CONFIG_IMAGE_SIZE]:
            frame = letterbox_resize(
                frame,
                self._config[CONFIG_IMAGE_SIZE],
                self._config[CONFIG_IMAGE_SIZE],
            )
        return cv2.imencode(".jpg", frame)[1].tobytes()

    def postprocess(self, detections):
        """Return CodeProject.AI detections as DetectedObject."""
        objects = []
        for detection in detections:
            objects.append(
                DetectedObject.from_absolute_letterboxed(
                    detection["label"],
                    detection["confidence"],
                    detection["x_min"],
                    detection["y_min"],
                    detection["x_max"],
                    detection["y_max"],
                    frame_res=self._camera.resolution,
                    model_res=self._image_resolution,
                )
            )
        return objects

    def return_objects(self, frame):
        """Perform object detection."""
        try:
            detections = self._detector.detect(frame)
        except cpai.CodeProjectAIException as exception:
            LOGGER.error("Error calling CodeProject.AI: %s", exception)
            return []

        return self.postprocess(detections)
