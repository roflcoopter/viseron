"""Frame read from FFmpeg."""
import logging
from typing import List

import cv2
import numpy as np

from viseron.detector.detected_object import DetectedObject

LOGGER = logging.getLogger(__name__)


class Frame:
    """Represents a frame read from FFMpeg."""

    def __init__(
        self,
        cvt_color,
        color_plane_width,
        color_plane_height,
        raw_frame,
        frame_width,
        frame_height,
    ):
        self._cvt_color = cvt_color
        self._color_plane_width = color_plane_width
        self._color_plane_height = color_plane_height
        self._raw_frame = raw_frame
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._decoded_frame = None
        self._decoded_frame_umat = None
        self._decoded_frame_umat_rgb = None
        self._decoded_frame_mat_rgb = None
        self._resized_frames = {}
        self._preprocessed_frames = {}
        self._objects: List[DetectedObject] = []
        self._motion_contours = None

    def decode_frame(self):
        """Decode raw frame to numpy array."""
        try:
            self._decoded_frame = np.frombuffer(self.raw_frame, np.uint8).reshape(
                self._color_plane_height, self._color_plane_width
            )
        except ValueError:
            LOGGER.warning("Failed to decode frame")
            return False
        return True

    def resize(self, decoder_name, width, height):
        """Resize and store frame."""
        self._resized_frames[decoder_name] = cv2.resize(
            self.decoded_frame_umat_rgb,
            (width, height),
            interpolation=cv2.INTER_LINEAR,
        )

    def get_resized_frame(self, decoder_name: str):
        """Fetch a stored frame."""
        return self._resized_frames.get(decoder_name, self.decoded_frame_umat_rgb)

    def save_preprocessed_frame(self, decoder_name: str, frame):
        """Store a frame returned from a preprocessor."""
        self._preprocessed_frames[decoder_name] = frame

    def get_preprocessed_frame(self, decoder_name: str):
        """Return stored from from a preprocessor."""
        return self._preprocessed_frames.get(
            decoder_name, self.get_resized_frame(decoder_name)
        )

    @property
    def raw_frame(self):
        """Return raw frame."""
        return self._raw_frame

    @property
    def frame_width(self):
        """Return frame width."""
        return self._frame_width

    @property
    def frame_height(self):
        """Return frame height."""
        return self._frame_height

    @property
    def decoded_frame(self):
        """Return decoded frame. Decodes frame if not already done."""
        if self._decoded_frame is None:
            self._decoded_frame = self.decode_frame()
        return self._decoded_frame

    @property
    def decoded_frame_umat(self):
        """Return decoded frame in UMat format. Decodes frame if not already done."""
        if self._decoded_frame_umat is None:
            self._decoded_frame_umat = cv2.UMat(self.decoded_frame)
        return self._decoded_frame_umat

    @property
    def decoded_frame_umat_rgb(self):
        """Return decoded frame in RGB UMat format.

        Decodes frame if not already done.
        """
        if self._decoded_frame_umat_rgb is None:
            self._decoded_frame_umat_rgb = cv2.cvtColor(
                self.decoded_frame_umat, self._cvt_color
            )
        return self._decoded_frame_umat_rgb

    @property
    def decoded_frame_mat_rgb(self):
        """Return decoded frame in RGB Mat format.

        Decodes frame if not already done.
        """
        if self._decoded_frame_mat_rgb is None:
            self._decoded_frame_mat_rgb = self.decoded_frame_umat_rgb.get()
        return self._decoded_frame_mat_rgb

    @property
    def objects(self) -> List[DetectedObject]:
        """Return all detected objects in frame."""
        return self._objects

    @objects.setter
    def objects(self, objects):
        self._objects = objects

    @property
    def motion_contours(self):
        """Return all motion contours in frame."""
        return self._motion_contours

    @motion_contours.setter
    def motion_contours(self, motion_contours):
        self._motion_contours = motion_contours
