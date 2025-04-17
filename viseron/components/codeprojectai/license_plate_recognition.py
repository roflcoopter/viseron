"""CodeProject.AI license plate recognition."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import codeprojectai.core as cpai
import cv2
import numpy as np

from viseron.domains.license_plate_recognition import (
    AbstractLicensePlateRecognition,
    DetectedLicensePlate,
)
from viseron.helpers import (
    calculate_absolute_coords,
    calculate_relative_coords,
    convert_letterboxed_bbox,
    letterbox_resize,
)

from .const import (
    COMPONENT,
    CONFIG_HOST,
    CONFIG_LICENSE_PLATE_RECOGNITION,
    CONFIG_MIN_CONFIDENCE,
    CONFIG_PORT,
    CONFIG_TIMEOUT,
    PLATE_RECOGNITION_URL_BASE,
)

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.object_detector.detected_object import DetectedObject
    from viseron.domains.post_processor import PostProcessorFrame

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the codeprojectai license_plate_recognition domain."""
    LicensePlateRecognition(vis, config, identifier)

    return True


class LicensePlateRecognition(AbstractLicensePlateRecognition):
    """CodeProject.AI license plate recognition processor."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_LICENSE_PLATE_RECOGNITION], camera_identifier
        )

        self._cpai_config = config
        self._cpai = CodeProjectAIALPR(
            host=config[CONFIG_HOST],
            port=config[CONFIG_PORT],
            timeout=config[CONFIG_TIMEOUT],
            min_confidence=config[CONFIG_LICENSE_PLATE_RECOGNITION][
                CONFIG_MIN_CONFIDENCE
            ],
        )

    def preprocess(self, frame) -> np.ndarray:
        """Preprocess frame."""
        return frame

    def _process_frame(
        self, frame: np.ndarray, detected_object: DetectedObject
    ) -> list[DetectedLicensePlate]:
        """Process frame."""
        detections: list[DetectedLicensePlate] = []
        x1, y1, x2, y2 = calculate_absolute_coords(
            (
                detected_object.rel_x1,
                detected_object.rel_y1,
                detected_object.rel_x2,
                detected_object.rel_y2,
            ),
            self._camera.resolution,
        )
        cropped_frame = frame[y1:y2, x1:x2].copy()
        height, width, _ = cropped_frame.shape
        max_dimension = max(width, height)
        cropped_frame = letterbox_resize(cropped_frame, max_dimension, max_dimension)

        try:
            result = self._cpai.detect(cv2.imencode(".jpg", cropped_frame)[1].tobytes())
        except cpai.CodeProjectAIException as error:
            self._logger.error("Error calling CodeProject.AI: %s", error)
            return detections

        self._logger.debug("License plate recognition result: %s", result)

        if not result["success"]:
            return detections

        for detection in sorted(result["predictions"], key=lambda x: x["confidence"]):
            # Convert coordinates from the letterboxed frame to the cropped frame
            cropped_frame_bbox = convert_letterboxed_bbox(
                width,
                height,
                max_dimension,
                max_dimension,
                (
                    detection["x_min"],
                    detection["y_min"],
                    detection["x_max"],
                    detection["y_max"],
                ),
                return_absolute=True,
            )

            # Convert coordinates from the cropped frame to the original frame
            original_frame_bbox = (
                cropped_frame_bbox[0] + x1,
                cropped_frame_bbox[1] + y1,
                cropped_frame_bbox[2] + x1,
                cropped_frame_bbox[3] + y1,
            )
            rel_x1, rel_y1, rel_x2, rel_y2 = calculate_relative_coords(
                original_frame_bbox, self._camera.resolution
            )

            detections.append(
                DetectedLicensePlate(
                    plate=detection["plate"],
                    confidence=detection["confidence"],
                    rel_x1=rel_x1,
                    rel_y1=rel_y1,
                    rel_x2=rel_x2,
                    rel_y2=rel_y2,
                    detected_object=detected_object,
                )
            )
        return detections

    def license_plate_recognition(
        self, post_processor_frame: PostProcessorFrame
    ) -> list[DetectedLicensePlate]:
        """Perform license plate recognition."""
        detections = []
        for detected_object in post_processor_frame.filtered_objects:
            detections += self._process_frame(
                post_processor_frame.frame, detected_object
            )
        return detections


class CodeProjectAIALPR:
    """Work with license plate recognition."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout: int,
        min_confidence: float,
    ) -> None:
        self.port = port
        self.timeout = timeout
        self.min_confidence = min_confidence

        self._url_base = PLATE_RECOGNITION_URL_BASE.format(host=host, port=port)

    def detect(self, image_bytes: bytes):
        """Process image_bytes and detect."""
        response = cpai.process_image(
            url=self._url_base,
            image_bytes=image_bytes,
            min_confidence=self.min_confidence,
            timeout=self.timeout,
        )
        return response
