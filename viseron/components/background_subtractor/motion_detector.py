"""Background subtractor motion detection."""
from __future__ import annotations

import cv2
import numpy as np

from viseron import Viseron
from viseron.domains.motion_detector import AbstractMotionDetectorScanner
from viseron.domains.motion_detector.const import CONFIG_CAMERAS, DOMAIN
from viseron.domains.motion_detector.contours import Contours

from .const import COMPONENT, CONFIG_ALPHA, CONFIG_THRESHOLD


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the background_subtractor motion_detector domain."""
    MotionDetector(vis, config[DOMAIN], identifier)

    return True


class MotionDetector(AbstractMotionDetectorScanner):
    """Perform motion detection."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        super().__init__(vis, COMPONENT, config, camera_identifier)
        self._camera_config = config[CONFIG_CAMERAS][camera_identifier]

        self._avg: np.ndarray | None = None

        vis.register_domain(DOMAIN, camera_identifier, self)

    def preprocess(self, frame: np.ndarray):
        """Resize the frame to the desired width and height."""
        return cv2.resize(
            frame,
            self._resolution,
            interpolation=cv2.INTER_LINEAR,
        )

    def return_motion(self, frame: np.ndarray) -> Contours:
        """Perform motion detection and return Contours."""
        frame = cv2.GaussianBlur(frame, (21, 21), 0)

        # if the average frame is None, initialize it
        if self._avg is None:
            self._avg = frame.astype("float")
            return Contours([], self._resolution)

        # accumulate the weighted average between the current frame and
        # previous frames, then compute the difference between the current
        # frame and running average.
        cv2.accumulateWeighted(frame, self._avg, self._camera_config[CONFIG_ALPHA])
        frame_delta = cv2.absdiff(frame, cv2.convertScaleAbs(self._avg))

        # threshold the delta image, dilate the thresholded image to fill
        # in holes, then find contours on thresholded image
        thresh = cv2.threshold(
            frame_delta, self._camera_config[CONFIG_THRESHOLD], 255, cv2.THRESH_BINARY
        )[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        return Contours(
            cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
            self._resolution,
        )
