"""fast-alpr license plate recognition."""

from __future__ import annotations

import logging
import statistics
from typing import TYPE_CHECKING

import cv2
import numpy as np
from fast_alpr import ALPR

from viseron.domains.license_plate_recognition import (
    AbstractLicensePlateRecognition,
    DetectedLicensePlate,
)
from viseron.domains.license_plate_recognition.const import CONFIG_MIN_CONFIDENCE
from viseron.exceptions import DomainNotReady
from viseron.helpers import calculate_absolute_coords, calculate_relative_coords

from .const import (
    COMPONENT,
    CONFIG_DETECTOR_CONF_THRESH,
    CONFIG_DETECTOR_MODEL,
    CONFIG_DEVICE,
    CONFIG_DISCARD_UNRECOGNIZED_PLATES,
    CONFIG_LICENSE_PLATE_RECOGNITION,
    CONFIG_OCR_MODEL,
    INSTANCES,
    LOCK,
)

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.object_detector.detected_object import DetectedObject
    from viseron.domains.post_processor import PostProcessorFrame

LOGGER = logging.getLogger(__name__)

DEVICE_PROVIDERS = {
    "cuda": ["CUDAExecutionProvider", "CPUExecutionProvider"],
    "cpu": ["CPUExecutionProvider"],
    "auto": None,
}


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the fastalpr license_plate_recognition domain."""
    LicensePlateRecognition(vis, config, identifier)

    return True


class LicensePlateRecognition(AbstractLicensePlateRecognition):
    """fast-alpr license plate recognition processor."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_LICENSE_PLATE_RECOGNITION], camera_identifier
        )

        self._alpr = self._get_alpr(vis, self._config)

    @staticmethod
    def _get_alpr(vis: Viseron, config) -> ALPR:
        """Get a shared ALPR instance for the given config, creating it if needed.

        ALPR instances are cached and shared across cameras that use identical
        model settings, since loading the ONNX models is expensive and
        onnxruntime sessions are thread-safe for concurrent predict() calls.
        """
        device = config[CONFIG_DEVICE]
        cache_key = (
            config[CONFIG_DETECTOR_MODEL],
            config[CONFIG_DETECTOR_CONF_THRESH],
            config[CONFIG_OCR_MODEL],
            device,
        )

        component_data = vis.data[COMPONENT]
        with component_data[LOCK]:
            alpr = component_data[INSTANCES].get(cache_key, None)
            if alpr is not None:
                return alpr

            try:
                alpr = ALPR(
                    detector_model=config[CONFIG_DETECTOR_MODEL],
                    detector_conf_thresh=config[CONFIG_DETECTOR_CONF_THRESH],
                    detector_providers=DEVICE_PROVIDERS[device],
                    ocr_model=config[CONFIG_OCR_MODEL],
                    ocr_device=device,
                )
            except Exception as error:
                LOGGER.error("Failed to load fast-alpr models: %s", error)
                raise DomainNotReady from error

            component_data[INSTANCES][cache_key] = alpr
            return alpr

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame.

        Frames from the post processor are decoded as RGB, but fast-alpr expects
        BGR (it forwards frames to cv2/onnxruntime models trained on BGR data).
        """
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

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
        cropped_frame = frame[y1:y2, x1:x2]

        for result in self._alpr.predict(cropped_frame):
            if result.ocr is None:
                continue

            if not result.ocr.text and self._config[CONFIG_DISCARD_UNRECOGNIZED_PLATES]:
                continue

            confidence = (
                statistics.mean(result.ocr.confidence)
                if isinstance(result.ocr.confidence, list)
                else result.ocr.confidence
            )
            if confidence < self._config[CONFIG_MIN_CONFIDENCE]:
                continue

            bbox = result.detection.bounding_box
            # Convert coordinates from the cropped frame to the original frame
            original_frame_bbox = (
                bbox.x1 + x1,
                bbox.y1 + y1,
                bbox.x2 + x1,
                bbox.y2 + y1,
            )
            rel_x1, rel_y1, rel_x2, rel_y2 = calculate_relative_coords(
                original_frame_bbox, self._camera.resolution
            )

            detections.append(
                DetectedLicensePlate(
                    plate=result.ocr.text,
                    confidence=confidence,
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
