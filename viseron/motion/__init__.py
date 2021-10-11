"""Handles motion detection."""
from __future__ import annotations

import importlib
import logging
from abc import ABC, abstractmethod
from queue import Queue
from typing import TYPE_CHECKING

import cv2
import numpy as np
from voluptuous import PREVENT_EXTRA

from viseron import helpers
from viseron.camera import FFMPEGCamera, FrameDecoder
from viseron.camera.frame_decoder import FrameToScan
from viseron.config.config_motion_detection import MotionDetectionConfig
from viseron.const import (
    TOPIC_FRAME_DECODE_MOTION,
    TOPIC_FRAME_PROCESSED_MOTION,
    TOPIC_FRAME_SCAN_MOTION,
)
from viseron.data_stream import DataStream
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron.config import NVRConfig


class Contours:
    """Represents motion contours."""

    def __init__(self, contours, resolution):
        self._contours = contours
        self._rel_contours = helpers.calculate_relative_contours(contours, resolution)

        scale_factor = resolution[0] * resolution[1]
        self._contour_areas = [cv2.contourArea(c) / scale_factor for c in contours]
        self._max_area = round(max(self._contour_areas, default=0), 5)

    @property
    def contours(self):
        """Return motion contours."""
        return self._contours

    @property
    def rel_contours(self):
        """Return contours with relative coordinates."""
        return self._rel_contours

    @property
    def contour_areas(self):
        """Return size of contours."""
        return self._contour_areas

    @property
    def max_area(self):
        """Return the size of the biggest contour."""
        return self._max_area


class AbstractMotionDetection(ABC):
    """Abstract Motion Detection."""

    def preprocess(self, frame_to_scan: FrameToScan):  # pylint: disable=no-self-use
        """Preprocessor function that runs before detection."""
        return frame_to_scan

    @abstractmethod
    def detect(self, frame_to_scan: FrameToScan) -> Contours:
        """Perform motion detection."""


class AbstractMotionDetectionConfig(ABC, MotionDetectionConfig):
    """Abstract Motion Detection Config."""

    SCHEMA = MotionDetectionConfig.schema.extend({}, extra=PREVENT_EXTRA)


class MotionDetection:
    """Subscribe to frames and run motion detection."""

    def __init__(self, config: NVRConfig, camera: FFMPEGCamera):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        self._logger.debug(
            f"Initializing motion detector {config.motion_detection.type}"
        )

        self._config = config

        self._resolution = (
            config.motion_detection.width,
            config.motion_detection.height,
        )

        self._mask = None
        if config.motion_detection.mask:
            self._logger.debug("Creating mask")
            # Scale mask to fit resized frame
            scaled_mask = []
            for point_list in config.motion_detection.mask:
                rel_mask = np.divide((point_list), camera.resolution)
                scaled_mask.append(
                    np.multiply(rel_mask, self._resolution).astype("int32")
                )

            mask = np.zeros(
                (config.motion_detection.width, config.motion_detection.height, 3),
                np.uint8,
            )
            mask[:] = 255

            cv2.fillPoly(mask, pts=scaled_mask, color=(0, 0, 0))
            self._mask = np.where(mask[:, :, 0] == [0])

        self._topic_scan_motion = f"{config.camera.name_slug}/{TOPIC_FRAME_SCAN_MOTION}"
        self.topic_processed_motion = (
            f"{config.camera.name_slug}/{TOPIC_FRAME_PROCESSED_MOTION}"
        )

        self._motion_detector = importlib.import_module(  # type: ignore
            "viseron.motion." + config.motion_detection.type
        ).MotionDetection(self._logger, config.motion_detection, self._mask)

        self._motion_detection_queue: Queue[  # pylint: disable=unsubscriptable-object
            FrameToScan,
        ] = Queue(maxsize=5)
        motion_detection_thread = RestartableThread(
            name=__name__ + "." + config.camera.name_slug,
            target=self.motion_detection,
            daemon=True,
            register=True,
        )
        motion_detection_thread.start()

        FrameDecoder(
            self._logger,
            self._config,
            f"{config.camera.name_slug}.motion_detection",
            config.motion_detection.fps,
            camera.stream,
            camera.decode_error,
            TOPIC_FRAME_DECODE_MOTION,
            TOPIC_FRAME_SCAN_MOTION,
            preprocess_callback=self._motion_detector.preprocess,
        )

        DataStream.subscribe_data(self._topic_scan_motion, self._motion_detection_queue)
        self._logger.debug("Motion detector initialized")

    def motion_detection(self):
        """Perform motion detection and publish the results."""
        while True:
            frame_to_scan: FrameToScan = self._motion_detection_queue.get()
            frame_to_scan.frame.motion_contours = self._motion_detector.detect(
                frame_to_scan
            )
            DataStream.publish_data(self.topic_processed_motion, frame_to_scan)
