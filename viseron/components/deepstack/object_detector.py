"""Deepstack object detector."""
import logging

import cv2
import deepstack.core as ds

from viseron import Viseron
from viseron.domains.object_detector import AbstractObjectDetector
from viseron.domains.object_detector.const import DOMAIN
from viseron.domains.object_detector.detected_object import DetectedObject

from .const import (
    COMPONENT,
    CONFIG_API_KEY,
    CONFIG_CUSTOM_MODEL,
    CONFIG_HOST,
    CONFIG_IMAGE_HEIGHT,
    CONFIG_IMAGE_WIDTH,
    CONFIG_OBJECT_DETECTOR,
    CONFIG_PORT,
    CONFIG_TIMEOUT,
)

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the deepstack object_detector domain."""
    ObjectDetector(vis, config, identifier)

    return True


class ObjectDetector(AbstractObjectDetector):
    """Deepstack object detection."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_OBJECT_DETECTOR], camera_identifier
        )

        self._ds_config = config
        self._detector = ds.DeepstackObject(
            ip=config[CONFIG_HOST],
            port=config[CONFIG_PORT],
            api_key=config[CONFIG_API_KEY],
            timeout=config[CONFIG_TIMEOUT],
            min_confidence=self.min_confidence,
            custom_model=self._config[CONFIG_CUSTOM_MODEL],
        )

        self._image_resolution = (
            self._config[CONFIG_IMAGE_WIDTH]
            if self._config[CONFIG_IMAGE_WIDTH]
            else self._camera.resolution[0],
            self._config[CONFIG_IMAGE_HEIGHT]
            if self._config[CONFIG_IMAGE_HEIGHT]
            else self._camera.resolution[1],
        )

        vis.register_domain(DOMAIN, camera_identifier, self)

    def preprocess(self, frame):
        """Preprocess frame before detection."""
        if self._config[CONFIG_IMAGE_WIDTH] and self._config[CONFIG_IMAGE_HEIGHT]:
            frame = cv2.resize(
                frame,
                (self._config[CONFIG_IMAGE_WIDTH], self._config[CONFIG_IMAGE_HEIGHT]),
                interpolation=cv2.INTER_LINEAR,
            )
        return cv2.imencode(".jpg", frame)[1].tobytes()

    def postprocess(self, detections):
        """Return deepstack detections as DetectedObject."""
        objects = []
        for detection in detections:
            objects.append(
                DetectedObject.from_absolute(
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
        except ds.DeepstackException as exception:
            LOGGER.error("Error calling deepstack: %s", exception)
            return []

        return self.postprocess(detections)
