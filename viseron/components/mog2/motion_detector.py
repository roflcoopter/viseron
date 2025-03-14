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


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the mog2 motion_detector domain."""
    MotionDetector(vis, config[DOMAIN], identifier)

    return True


class MotionDetector(AbstractMotionDetectorScanner):
    """Perform motion detection."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        super().__init__(vis, COMPONENT, config, camera_identifier)

        self._camera_config = config[CONFIG_CAMERAS][camera_identifier]
        self._bgsmog = cv2.createBackgroundSubtractorMOG2(
            self._camera_config[CONFIG_HISTORY],
            self._camera_config[CONFIG_THRESHOLD],
            self._camera_config[CONFIG_DETECT_SHADOWS],
        )

        self._empty_mat = cv2.Mat(np.empty((3, 3), np.uint8))
        vis.register_domain(DOMAIN, camera_identifier, self)

    def preprocess(self, frame):
        """Resize the frame to the desired width and height."""
        return cv2.resize(
            frame,
            self._resolution,
            interpolation=cv2.INTER_LINEAR,
        )

    def return_motion(self, frame) -> Contours:
        """Perform motion detection and return Contours."""
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
