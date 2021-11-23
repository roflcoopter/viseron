"""Frames shared in memory."""
import logging
import time
from multiprocessing import shared_memory

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
        name,
        color_plane_width,
        color_plane_height,
        pixel_format,
        resolution,
        camera_identifier,
        config=None,
    ):
        self.name = name
        self.color_plane_width = color_plane_width
        self.color_plane_height = color_plane_height
        self.pixel_format = pixel_format
        self.resolution = resolution
        self.camera_identifier = camera_identifier
        self.nvr_config = config
        self.capture_time = time.time()


class SharedFrames:
    """Byte frame shared in memory."""

    def __init__(self):
        self._frames = {}

    def create(self, size, name=None):
        """Create frame in shared memory."""
        shm_frame = shared_memory.SharedMemory(create=True, size=size, name=name)
        self._frames[shm_frame.name] = shm_frame
        return shm_frame

    def _get(self, name):
        """Return frame from shared memory."""
        if shm_frame := self._frames.get(name, None):
            return shm_frame

        shm_frame = shared_memory.SharedMemory(name=name)
        self._frames[shm_frame.name] = shm_frame
        return shm_frame

    def get_decoded_frame(self, shared_frame: SharedFrame) -> np.ndarray:
        """Return byte frame in numpy format."""
        shared_frame_numpy = f"{shared_frame.name}_numpy"
        if shm_frame := self._frames.get(shared_frame_numpy, None):
            return self._frames[shared_frame_numpy]

        shm_frame = self._get(shared_frame.name)
        self._frames[shared_frame_numpy] = np.ndarray(
            (shared_frame.color_plane_height, shared_frame.color_plane_width),
            dtype=np.uint8,
            buffer=shm_frame.buf,
        )
        return self._frames[shared_frame_numpy]

    def _color_convert(self, shared_frame: SharedFrame, color_model) -> np.ndarray:
        """Return decoded frame in specified color format."""
        shared_frame_name = f"{shared_frame.name}_{color_model}"
        shared_frame_numpy = f"{shared_frame.name}_{color_model}_numpy"
        pixel_format = PIXEL_FORMATS[shared_frame.pixel_format]
        if self._frames.get(shared_frame_numpy, None):
            return self._frames[shared_frame_numpy]

        decoded_frame = self.get_decoded_frame(shared_frame)
        try:
            shm_frame = self._get(shared_frame_name)
            shm_frame_numpy: np.ndarray = np.ndarray(
                (
                    shared_frame.resolution[1],
                    shared_frame.resolution[0],
                    pixel_format[color_model][CHANNELS],
                ),
                dtype=np.uint8,
                buffer=shm_frame.buf,
            )
        except FileNotFoundError:
            shm_frame = self.create(
                shared_frame.resolution[0]
                * shared_frame.resolution[1]
                * pixel_format[color_model][CHANNELS],
                name=shared_frame_name,
            )
            shm_frame_numpy = np.ndarray(
                (
                    shared_frame.resolution[1],
                    shared_frame.resolution[0],
                    pixel_format[color_model][CHANNELS],
                ),
                dtype=np.uint8,
                buffer=shm_frame.buf,
            )
            cv2.cvtColor(
                decoded_frame, pixel_format[color_model][CONVERTER], shm_frame_numpy
            )

        self._frames[shared_frame_name] = shm_frame
        self._frames[shared_frame_numpy] = shm_frame_numpy
        return shm_frame_numpy

    def get_decoded_frame_rgb(self, shared_frame: SharedFrame) -> np.ndarray:
        """Return decoded frame in rgb numpy format."""
        return self._color_convert(shared_frame, COLOR_MODEL_RGB)

    def get_decoded_frame_gray(self, shared_frame: SharedFrame) -> np.ndarray:
        """Return decoded frame in gray numpy format."""
        return self._color_convert(shared_frame, COLOR_MODEL_GRAY)

    def _close(self, name):
        try:
            frame = self._get(name)
            frame.close()
            del self._frames[name]
            del self._frames[f"{name}_numpy"]
        except (FileNotFoundError, KeyError):
            pass

    def close(self, shared_frame: SharedFrame):
        """Close frame in shared memory."""
        self._close(shared_frame.name)
        if isinstance(shared_frame, shared_memory.SharedMemory):
            return

        for color_model in PIXEL_FORMATS[shared_frame.pixel_format]:
            self._close(f"{shared_frame.name}_{color_model}")

    def _remove(self, name):
        try:
            frame = self._get(name)
            frame.close()
            frame.unlink()
            del self._frames[name]
            del self._frames[f"{name}_numpy"]
        except (FileNotFoundError, KeyError):
            pass

    def remove(self, shared_frame: SharedFrame):
        """Remove frame from shared memory."""
        self._remove(shared_frame.name)
        for color_model in PIXEL_FORMATS[shared_frame.pixel_format]:
            self._remove(f"{shared_frame.name}_{color_model}")
