"""Frames shared in memory."""

from __future__ import annotations

import logging
import time
import uuid

import cv2
import numpy as np

from viseron.helpers.decorators import return_copy

LOGGER = logging.getLogger(__name__)

PIXEL_FORMAT_YUV420P = "yuv420p"
PIXEL_FORMAT_NV12 = "nv12"

COLOR_MODEL_RGB = "rgb"
COLOR_MODEL_GRAY = "gray"

CONVERTER = "converter"
CHANNELS = "channels"

PIXEL_FORMATS = {
    PIXEL_FORMAT_YUV420P: {
        COLOR_MODEL_RGB: {
            CONVERTER: cv2.COLOR_YUV2BGR_I420,  # strange, but works
            CHANNELS: 3,
        },
        COLOR_MODEL_GRAY: {
            CONVERTER: cv2.COLOR_YUV2GRAY_I420,
            CHANNELS: 1,
        },
    },
    PIXEL_FORMAT_NV12: {
        COLOR_MODEL_RGB: {
            CONVERTER: cv2.COLOR_YUV2RGB_NV21,
            CHANNELS: 3,
        },
        COLOR_MODEL_GRAY: {
            CONVERTER: cv2.COLOR_YUV2GRAY_NV21,
            CHANNELS: 1,
        },
    },
}


class SharedFrame:
    """A frame shared in memory, along with its color converted copies."""

    def __init__(
        self,
        frame_bytes: bytes,
        color_plane_width: int,
        color_plane_height: int,
        pixel_format: str,
        resolution: tuple[int, int],
        camera_identifier: str,
    ) -> None:
        self.name = uuid.uuid4()
        self.color_plane_width = color_plane_width
        self.color_plane_height = color_plane_height
        self.pixel_format = pixel_format
        self.resolution = resolution
        self.camera_identifier = camera_identifier
        self.capture_time = time.time()
        self.decoded_frame = np.frombuffer(frame_bytes, np.uint8).reshape(
            color_plane_height, color_plane_width
        )
        self._color_converted: dict[str, np.ndarray] = {}

    def color_convert(self, color_model: str) -> np.ndarray:
        """Return the frame in the given color model, converting it once."""
        try:
            return self._color_converted[color_model]
        except KeyError:
            pass

        converted_frame = cv2.cvtColor(
            self.decoded_frame,
            PIXEL_FORMATS[self.pixel_format][color_model][CONVERTER],
        )
        self._color_converted[color_model] = converted_frame
        return converted_frame


class SharedFrames:
    """Access the frames held by a SharedFrame."""

    @staticmethod
    def get_decoded_frame(shared_frame: SharedFrame) -> np.ndarray:
        """Return byte frame in numpy format."""
        return shared_frame.decoded_frame

    @staticmethod
    @return_copy
    def get_decoded_frame_rgb(shared_frame: SharedFrame) -> np.ndarray:
        """Return decoded frame in rgb numpy format."""
        return shared_frame.color_convert(COLOR_MODEL_RGB)

    @staticmethod
    @return_copy
    def get_decoded_frame_gray(shared_frame: SharedFrame) -> np.ndarray:
        """Return decoded frame in gray numpy format."""
        return shared_frame.color_convert(COLOR_MODEL_GRAY)
