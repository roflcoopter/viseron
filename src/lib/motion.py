import logging
from queue import Queue
from threading import Thread

import cv2
import numpy as np

from const import TOPIC_FRAME_PROCESSED_MOTION, TOPIC_FRAME_SCAN_MOTION
from lib.data_stream import DataStream
from lib.helpers import calculate_relative_contours


class Contours:
    def __init__(self, contours, resolution):
        self._contours = contours
        self._rel_contours = calculate_relative_contours(contours, resolution)

        scale_factor = resolution[0] * resolution[1]
        self._contour_areas = [cv2.contourArea(c) / scale_factor for c in contours]
        self._max_area = round(max(self._contour_areas, default=0), 5)

    @property
    def contours(self):
        return self._contours

    @property
    def rel_contours(self):
        return self._rel_contours

    @property
    def contour_areas(self):
        return self._contour_areas

    @property
    def max_area(self):
        return self._max_area


class MotionDetection:
    def __init__(self, config, camera_resolution):
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
                rel_mask = np.divide((point_list), camera_resolution)
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

        self._motion_detection_queue = Queue(maxsize=5)
        motion_detection_thread = Thread(target=self.motion_detection)
        motion_detection_thread.daemon = True
        motion_detection_thread.start()

        DataStream.subscribe_data(self._topic_scan_motion, self._motion_detection_queue)
        self._logger.debug("Motion detector initialized")

    def detect(self, frame):
        gray = cv2.cvtColor(
            frame["frame"].get_resized_frame(frame["decoder_name"]), cv2.COLOR_RGB2GRAY
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
        while True:
            frame = self._motion_detection_queue.get()
            frame["frame"].motion_contours = self.detect(frame)
            DataStream.publish_data(self.topic_processed_motion, frame["frame"])
