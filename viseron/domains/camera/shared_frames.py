"""Frames shared in memory."""
from __future__ import annotations

import logging
import time
import uuid
from functools import lru_cache

import cv2
import numpy as np

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
    """Information about a frame shared in memory."""

    def __init__(
        self,
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


class SharedFrames:
    """Byte frame shared in memory."""

    def __init__(self) -> None:
        self._frames: dict[uuid.UUID | str, np.ndarray] = {}

    def create(self, shared_frame: SharedFrame, frame_bytes: bytes) -> None:
        """Create frame in shared memory."""
        self._frames[shared_frame.name] = np.frombuffer(frame_bytes, np.uint8).reshape(
            shared_frame.color_plane_height, shared_frame.color_plane_width
        )

    def get_decoded_frame(self, shared_frame: SharedFrame) -> np.ndarray:
        """Return byte frame in numpy format."""
        return self._frames[shared_frame.name]

    @lru_cache(maxsize=2)
    def _color_convert(self, shared_frame: SharedFrame, color_model: str) -> np.ndarray:
        """Return decoded frame in specified color format."""
        shared_frame_name = f"{shared_frame.name}_{color_model}"
        pixel_format = PIXEL_FORMATS[shared_frame.pixel_format]
        if self._frames.get(shared_frame_name, None) is not None:
            return self._frames[shared_frame_name]

        decoded_frame = self.get_decoded_frame(shared_frame).copy()
        decoded_frame = cv2.cvtColor(
            decoded_frame, pixel_format[color_model][CONVERTER]
        )

        self._frames[shared_frame_name] = decoded_frame
        return decoded_frame

    def get_decoded_frame_rgb(self, shared_frame: SharedFrame) -> np.ndarray:
        """Return decoded frame in rgb numpy format."""
        return self._color_convert(shared_frame, COLOR_MODEL_RGB)

    def get_decoded_frame_gray(self, shared_frame: SharedFrame) -> np.ndarray:
        """Return decoded frame in gray numpy format."""
        return self._color_convert(shared_frame, COLOR_MODEL_GRAY)

    def _remove(self, name) -> None:
        try:
            del self._frames[name]
        except KeyError:
            pass

    def remove(self, shared_frame: SharedFrame) -> None:
        """Remove frame from shared memory."""
        self._remove(shared_frame.name)
        for color_model in PIXEL_FORMATS[PIXEL_FORMAT_YUV420P]:
            self._remove(f"{shared_frame.name}_{color_model}")

    def remove_all(self) -> None:
        """Remove all frames still in shared memory."""
        for frame_name in self._frames.copy():
            self._remove(frame_name)
            for color_model in PIXEL_FORMATS[PIXEL_FORMAT_YUV420P]:
                self._remove(f"{frame_name}_{color_model}")
