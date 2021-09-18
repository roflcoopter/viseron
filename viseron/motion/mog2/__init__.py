"""Background Subtractor MOG2 motion detector."""

import cv2

from viseron.camera.frame_decoder import FrameToScan
from viseron.motion import AbstractMotionDetection, Contours

from .config import Config


class MotionDetection(AbstractMotionDetection):
    """Perform motion detection."""

    def __init__(self, logger, config: Config, mask):
        self._logger = logger
        self._config = config
        self._mask = mask

        self._bgsmog = cv2.createBackgroundSubtractorMOG2(
            self._config.history, self._config.threshold, self._config.detect_shadows
        )
        self._resolution = (
            config.width,
            config.height,
        )

    def preprocess(self, frame_to_scan: FrameToScan):
        """Resize the frame to the desired width and height."""
        frame_to_scan.frame.resize(
            frame_to_scan.decoder_name,
            self._config.width,
            self._config.height,
        )
        frame_to_scan.frame.save_preprocessed_frame(
            frame_to_scan.decoder_name,
            frame_to_scan.frame.get_resized_frame(frame_to_scan.decoder_name),
        )

    def detect(self, frame_to_scan: FrameToScan) -> Contours:
        """Perform motion detection and return Contours."""
        fgmask = self._bgsmog.apply(
            frame_to_scan.frame.get_preprocessed_frame(frame_to_scan.decoder_name),
            learningRate=self._config.learning_rate,
        )
        fgmask = cv2.erode(fgmask, None, iterations=1)
        fgmask = cv2.dilate(fgmask, None, iterations=4)

        frame = fgmask.get()
        if self._mask:
            frame[self._mask] = [0]

        return Contours(
            cv2.findContours(frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
            self._resolution,
        )
