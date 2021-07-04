"""Handles motion detection."""
from __future__ import annotations

import logging
from queue import Queue
from typing import TYPE_CHECKING

import cv2
import numpy as np

from viseron import helpers
from viseron.camera import FFMPEGCamera, FrameDecoder
from viseron.camera.frame_decoder import FrameToScan
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


class MotionDetection:
    """Subscribe to frames and run motion detection."""

    def __init__(self, config: NVRConfig, camera: FFMPEGCamera):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        if getattr(config.motion_detection.logging, "level", None):
            self._logger.setLevel(config.motion_detection.logging.level)
        elif getattr(config.camera.logging, "level", None):
            self._logger.setLevel(config.camera.logging.level)
        self._logger.debug("Initializing motion detector")

        self._config = config

        self._resolution = (
            config.motion_detection.width,
            config.motion_detection.height,
        )
        self._avg = None

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

        self._motion_detection_queue: Queue[  # pylint: disable=unsubscriptable-object
            FrameToScan
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
            config.motion_detection.interval,
            camera.stream,
            camera.decode_error,
            TOPIC_FRAME_DECODE_MOTION,
            TOPIC_FRAME_SCAN_MOTION,
            preprocess_callback=self.preprocess,
        )

        DataStream.subscribe_data(self._topic_scan_motion, self._motion_detection_queue)
        self._logger.debug("Motion detector initialized")

    def preprocess(self, frame_to_scan: FrameToScan):
        """Resize the frame to the desired width and height."""
        frame_to_scan.frame.resize(
            frame_to_scan.decoder_name,
            self._config.motion_detection.width,
            self._config.motion_detection.height,
        )
        frame_to_scan.frame.save_preprocessed_frame(
            frame_to_scan.decoder_name,
            frame_to_scan.frame.get_resized_frame(frame_to_scan.decoder_name),
        )

    def detect(self, frame_to_scan: FrameToScan) -> Contours:
        """Perform motion detection and return Contours."""
        gray = cv2.cvtColor(
            frame_to_scan.frame.get_preprocessed_frame(frame_to_scan.decoder_name),
            cv2.COLOR_RGB2GRAY,
        )
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        gray = gray.get()  # Convert from UMat to Mat
        if self._mask:
            gray[self._mask] = [0]

        # if the average frame is None, initialize it
        if self._avg is None:
            self._avg = gray.astype("float")

        # accumulate the weighted average between the current frame and
        # previous frames, then compute the difference between the current
        # frame and running average.
        cv2.accumulateWeighted(gray, self._avg, self._config.motion_detection.alpha)
        frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(self._avg))

        # threshold the delta image, dilate the thresholded image to fill
        # in holes, then find contours on thresholded image
        thresh = cv2.threshold(
            frame_delta, self._config.motion_detection.threshold, 255, cv2.THRESH_BINARY
        )[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        return Contours(
            cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
            self._resolution,
        )

    def motion_detection(self):
        """Perform motion detection and publish the results."""
        while True:
            frame_to_scan: FrameToScan = self._motion_detection_queue.get()
            frame_to_scan.frame.motion_contours = self.detect(frame_to_scan)
            DataStream.publish_data(self.topic_processed_motion, frame_to_scan)
