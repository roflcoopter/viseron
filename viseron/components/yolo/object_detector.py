"""YOLO object detector."""

import logging
from pathlib import Path
from typing import Any

import numpy as np
from ultralytics import YOLO
from ultralytics.engine.results import Results

from viseron import Viseron
from viseron.domains.object_detector import AbstractObjectDetector
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.exceptions import DomainNotReady

from .const import (
    COMPONENT,
    CONFIG_DEVICE,
    CONFIG_HALF_PRECISION,
    CONFIG_IOU,
    CONFIG_MIN_CONFIDENCE,
    CONFIG_MODEL_PATH,
    CONFIG_OBJECT_DETECTOR,
)

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config: dict[str, Any], identifier: str) -> bool:
    """Set up the YOLO object_detector domain."""
    ObjectDetector(vis, config, identifier)

    return True


class ObjectDetector(AbstractObjectDetector):
    """YOLO object detection."""

    def __init__(
        self, vis: Viseron, config: dict[str, Any], camera_identifier: str
    ) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_OBJECT_DETECTOR], camera_identifier
        )

        try:
            model = Path(self._config[CONFIG_MODEL_PATH])
            self._detector = YOLO(model)
        except Exception as error:
            LOGGER.error("YOLO model file not loaded: %s", error)
            raise DomainNotReady from error

        LOGGER.info(f"Loaded YOLO model: {model}")
        LOGGER.info(f"Labels: {self._detector.names}")

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame before detection."""
        return np.array(frame)

    def postprocess(self, results: list[Results]) -> list[DetectedObject]:
        """Return yolo detections as DetectedObject."""
        objects = []

        for result in results:
            if result.boxes is None or len(result.boxes) == 0:
                continue

            classes_names = result.names
            boxes = result.boxes

            for i in range(len(boxes)):  # pylint: disable=consider-using-enumerate
                cls = int(boxes[i].cls[0])
                [x1, y1, x2, y2] = boxes[i].xyxy[0]
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                objects.append(
                    DetectedObject.from_absolute(
                        label=classes_names[cls],
                        confidence=float(boxes[i].conf),
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        frame_res=self._camera.resolution,
                        model_res=result.orig_shape[::-1],
                    )
                )
        return objects

    def return_objects(self, frame: np.ndarray) -> list[DetectedObject]:
        """Perform object detection."""
        try:
            results = self._detector.predict(
                frame,
                conf=self._config[CONFIG_MIN_CONFIDENCE],
                iou=self._config[CONFIG_IOU],
                half=self._config[CONFIG_HALF_PRECISION],
                device=self._config[CONFIG_DEVICE],
                verbose=False,
            )
        except ValueError as error:
            LOGGER.error(f"Error calling yolo prediction check yolo config: {error}")
            return []

        return self.postprocess(results)

    def unload(self) -> None:
        """Unload the object detector."""
        super().unload()
        del self._detector
