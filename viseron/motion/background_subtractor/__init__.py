"""Background subtractor motion detection."""
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

        self._avg = None
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
        gray = cv2.cvtColor(
            frame_to_scan.frame.get_preprocessed_frame(frame_to_scan.decoder_name),
            cv2.COLOR_RGB2GRAY,
        )
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        gray = gray.get()
        if self._mask:
            gray[self._mask] = [0]

        # if the average frame is None, initialize it
        if self._avg is None:
            self._avg = gray.astype("float")
            return Contours([], self._resolution)

        # accumulate the weighted average between the current frame and
        # previous frames, then compute the difference between the current
        # frame and running average.
        cv2.accumulateWeighted(gray, self._avg, self._config.alpha)
        frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(self._avg))

        # threshold the delta image, dilate the thresholded image to fill
        # in holes, then find contours on thresholded image
        thresh = cv2.threshold(
            frame_delta, self._config.threshold, 255, cv2.THRESH_BINARY
        )[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        return Contours(
            cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
            self._resolution,
        )
