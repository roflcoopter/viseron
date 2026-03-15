"""Background Subtractor MOG2 motion detector."""

import cv2
import numpy as np

from viseron import Viseron
from viseron.domains.motion_detector import AbstractMotionDetectorScanner
from viseron.domains.motion_detector.const import CONFIG_CAMERAS, DOMAIN
from viseron.domains.motion_detector.contours import Contours

from .const import (
    COMPONENT,
    CONFIG_DETECT_SHADOWS,
    CONFIG_HISTORY,
    CONFIG_LEARNING_RATE,
    CONFIG_THRESHOLD,
)


def setup(vis: Viseron, config: dict, identifier: str) -> bool:
    """Set up the mog2 motion_detector domain."""
    MotionDetector(vis, config[DOMAIN], identifier)

    return True


class MotionDetector(AbstractMotionDetectorScanner):
    """Perform motion detection."""

    def __init__(self, vis: Viseron, config: dict, camera_identifier: str) -> None:
        super().__init__(vis, COMPONENT, config, camera_identifier)

        self._camera_config = config[CONFIG_CAMERAS][camera_identifier]
        self._bgsmog = cv2.createBackgroundSubtractorMOG2(
            self._camera_config[CONFIG_HISTORY],
            self._camera_config[CONFIG_THRESHOLD],
            self._camera_config[CONFIG_DETECT_SHADOWS],
        )

        self._empty_mat = cv2.Mat(np.empty((3, 3), np.uint8))
        self._first_frame = True

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Resize the frame to the desired width and height."""
        return cv2.resize(
            frame,
            self._resolution,
            interpolation=cv2.INTER_LINEAR,
        )

    def return_motion(self, frame: np.ndarray) -> Contours:
        """Perform motion detection and return Contours."""
        if self._first_frame:
            self._first_frame = False
            self._bgsmog.apply(frame, learningRate=1.0)
            return Contours([], self._resolution)

        fgmask = self._bgsmog.apply(
            frame,
            learningRate=self._camera_config[CONFIG_LEARNING_RATE],
        )
        fgmask = cv2.erode(fgmask, self._empty_mat, iterations=1)
        fgmask = cv2.dilate(fgmask, self._empty_mat, iterations=4)

        return Contours(
            cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
            self._resolution,
        )
