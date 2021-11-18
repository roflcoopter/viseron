"""Frames shared in memory."""
import time
from multiprocessing import shared_memory

import cv2
import numpy as np


class SharedFrame:
    """Information about a frame shared in memory."""

    def __init__(
        self,
        name,
        color_plane_width,
        color_plane_height,
        color_converter,
        resolution,
        camera_identifier,
        config=None,
    ):
        self.name = name
        self.color_plane_width = color_plane_width
        self.color_plane_height = color_plane_height
        self.color_converter = color_converter
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

    def get_decoded_frame_rgb(self, shared_frame: SharedFrame) -> np.ndarray:
        """Return decoded frame in rgb numpy format."""
        shared_frame_rgb_name = f"{shared_frame.name}_rgb"
        shared_frame_rgb_numpy = f"{shared_frame.name}_rgb_numpy"
        if self._frames.get(shared_frame_rgb_numpy, None):
            return self._frames[shared_frame_rgb_numpy]

        decoded_frame = self.get_decoded_frame(shared_frame)
        try:
            shm_frame = self._get(shared_frame_rgb_name)
            shm_frame_rgb_numpy: np.ndarray = np.ndarray(
                (shared_frame.resolution[1], shared_frame.resolution[0], 3),
                dtype=np.uint8,
                buffer=shm_frame.buf,
            )
        except FileNotFoundError:
            shm_frame = self.create(
                shared_frame.resolution[0] * shared_frame.resolution[1] * 3,
                name=shared_frame_rgb_name,
            )
            shm_frame_rgb_numpy = np.ndarray(
                (shared_frame.resolution[1], shared_frame.resolution[0], 3),
                dtype=np.uint8,
                buffer=shm_frame.buf,
            )
            cv2.cvtColor(
                decoded_frame, shared_frame.color_converter, shm_frame_rgb_numpy
            )

        self._frames[shared_frame_rgb_name] = shm_frame
        self._frames[shared_frame_rgb_numpy] = shm_frame_rgb_numpy
        return shm_frame_rgb_numpy

    def close(self, shared_frame: SharedFrame):
        """Close frame in shared memory."""
        frame = self._get(shared_frame.name)
        frame.close()
        del self._frames[shared_frame.name]
        try:
            del self._frames[f"{shared_frame.name}_numpy"]
        except KeyError:
            pass

        frame_rgb_name = f"{shared_frame.name}_rgb"
        try:
            frame = self._get(frame_rgb_name)
            frame.close()
            del self._frames[frame_rgb_name]
            del self._frames[f"{frame_rgb_name}_numpy"]
        except (FileNotFoundError, KeyError):
            pass

    def remove(self, shared_frame: SharedFrame):
        """Remove frame from shared memory."""
        frame = self._get(shared_frame.name)
        frame.close()
        frame.unlink()
        del self._frames[shared_frame.name]
        try:
            del self._frames[f"{shared_frame.name}_numpy"]
        except KeyError:
            pass

        frame_rgb_name = f"{shared_frame.name}_rgb"
        try:
            frame = self._get(frame_rgb_name)
            frame.close()
            frame.unlink()
            del self._frames[frame_rgb_name]
            del self._frames[f"{frame_rgb_name}_numpy"]
        except (FileNotFoundError, KeyError):
            pass
