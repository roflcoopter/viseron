"""Deepstack object detector."""
import logging

import cv2
import deepstack.core as ds

from viseron.camera.frame_decoder import FrameToScan
from viseron.detector import AbstractObjectDetection
from viseron.detector.detected_object import DetectedObject

from .config import Config

LOGGER = logging.getLogger(__name__)


class ObjectDetection(AbstractObjectDetection):
    """Deepstack object detection."""

    def __init__(self, config: Config):
        self._config = config
        self._detector = ds.DeepstackObject(
            ip=config.host,
            port=config.port,
            api_key=config.api_key,
            timeout=config.timeout,
            min_confidence=0.1,
            custom_model=config.custom_model,
        )

    def preprocess(self, frame_to_scan: FrameToScan):
        """Preprocess frame before detection."""
        if self._config.image_width and self._config.image_height:
            frame_to_scan.frame.resize(
                frame_to_scan.decoder_name,
                self._config.image_width,
                self._config.image_height,
            )
        frame_to_scan.frame.save_preprocessed_frame(
            frame_to_scan.decoder_name,
            cv2.imencode(
                ".jpg",
                frame_to_scan.frame.get_resized_frame(frame_to_scan.decoder_name),
            )[1].tobytes(),
        )

    def postprocess(self, detections, frame: FrameToScan):
        """Return deepstack detections as DetectedObject."""
        objects = []
        for detection in detections:
            objects.append(
                DetectedObject(
                    detection["label"],
                    detection["confidence"],
                    detection["x_min"],
                    detection["y_min"],
                    detection["x_max"],
                    detection["y_max"],
                    relative=False,
                    image_res=(
                        self._config.image_width
                        if self._config.image_width
                        else frame.stream_width,
                        self._config.image_height
                        if self._config.image_height
                        else frame.stream_height,
                    ),
                )
            )
        return objects

    def return_objects(self, frame_to_scan: FrameToScan):
        """Perform object detection."""
        try:
            detections = self._detector.detect(
                frame_to_scan.frame.get_preprocessed_frame(frame_to_scan.decoder_name)
            )
        except ds.DeepstackException as exception:
            LOGGER.error("Error calling deepstack: %s", exception)
            return []

        return self.postprocess(detections, frame=frame_to_scan)
