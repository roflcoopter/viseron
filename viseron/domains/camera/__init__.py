"""Camera domain."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Any, Dict, Tuple

import cv2
import numpy as np
import voluptuous as vol

from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.helpers import slugify
from viseron.helpers.logs import SensitiveInformationFilter
from viseron.helpers.validators import ensure_slug

DOMAIN = "camera"

CONFIG_MJPEG_WIDTH = "width"
CONFIG_MJPEG_HEIGHT = "height"
CONFIG_MJPEG_DRAW_OBJECTS = "draw_objects"
CONFIG_MJPEG_DRAW_MOTION = "draw_motion"
CONFIG_MJPEG_DRAW_MOTION_MASK = "draw_motion_mask"
CONFIG_MJPEG_DRAW_OBJECT_MASK = "draw_object_mask"
CONFIG_MJPEG_DRAW_ZONES = "draw_zones"
CONFIG_MJPEG_ROTATE = "rotate"
CONFIG_MJPEG_MIRROR = "mirror"

DEFAULT_MJPEG_WIDTH = 0
DEFAULT_MJPEG_HEIGHT = 0
DEFAULT_MJPEG_DRAW_OBJECTS = False
DEFAULT_MJPEG_DRAW_MOTION = False
DEFAULT_MJPEG_DRAW_MOTION_MASK = False
DEFAULT_MJPEG_DRAW_OBJECT_MASK = False
DEFAULT_MJPEG_DRAW_ZONES = False
DEFAULT_MJPEG_ROTATE = 0
DEFAULT_MJPEG_MIRROR = False

COERCE_INT = vol.Schema(vol.All(vol.Any(int, str), vol.Coerce(int)))

STR_BOOL_BYTES = vol.Schema(vol.Any(str, bool, bytes))

MJPEG_STREAM_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_MJPEG_WIDTH, default=DEFAULT_MJPEG_WIDTH): COERCE_INT,
        vol.Optional(CONFIG_MJPEG_HEIGHT, default=DEFAULT_MJPEG_HEIGHT): COERCE_INT,
        vol.Optional(
            CONFIG_MJPEG_DRAW_OBJECTS, default=DEFAULT_MJPEG_DRAW_OBJECTS
        ): STR_BOOL_BYTES,
        vol.Optional(
            CONFIG_MJPEG_DRAW_MOTION, default=DEFAULT_MJPEG_DRAW_MOTION
        ): STR_BOOL_BYTES,
        vol.Optional(
            CONFIG_MJPEG_DRAW_MOTION_MASK, default=DEFAULT_MJPEG_DRAW_MOTION_MASK
        ): STR_BOOL_BYTES,
        vol.Optional(
            CONFIG_MJPEG_DRAW_OBJECT_MASK, default=DEFAULT_MJPEG_DRAW_OBJECT_MASK
        ): STR_BOOL_BYTES,
        vol.Optional(
            CONFIG_MJPEG_DRAW_ZONES, default=DEFAULT_MJPEG_DRAW_ZONES
        ): STR_BOOL_BYTES,
        vol.Optional(CONFIG_MJPEG_ROTATE, default=DEFAULT_MJPEG_ROTATE): COERCE_INT,
        vol.Optional(CONFIG_MJPEG_MIRROR, default=DEFAULT_MJPEG_MIRROR): STR_BOOL_BYTES,
    }
)

CONFIG_SAVE_TO_DISK = "save_to_disk"
CONFIG_FILENAME_PATTERN = "filename_pattern"
CONFIG_SEND_TO_MQTT = "send_to_mqtt"

DEFAULT_SAVE_TO_DISK = False
DEFAULT_FILENAME_PATTERN = "%H:%M:%S"
DEFAULT_SEND_TO_MQTT = False

THUMBNAIL_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_SAVE_TO_DISK, default=DEFAULT_SAVE_TO_DISK): bool,
        vol.Optional(CONFIG_FILENAME_PATTERN, default=DEFAULT_FILENAME_PATTERN): str,
        vol.Optional(CONFIG_SEND_TO_MQTT, default=DEFAULT_SEND_TO_MQTT): bool,
    }
)

CONFIG_LOOKBACK = "lookback"
CONFIG_IDLE_TIMEOUT = "IDLE_TIMEOUT"
CONFIG_RETAIN = "retain"
CONFIG_FOLDER = "folder"
CONFIG_FILENAME_PATTERN = "filename_pattern"
CONFIG_EXTENSION = "extension"
CONFIG_THUMBNAIL = "thumbnail"

DEFAULT_LOOKBACK = 5
DEFAULT_IDLE_TIMEOUT = 10
DEFAULT_RETAIN = 7
DEFAULT_FOLDER = "/recordings"
DEFAULT_FILENAME_PATTERN = "%H:%M:%S"
DEFAULT_EXTENSION = "mp4"
DEFAULT_THUMBNAIL: Dict[str, Any] = {}


RECORDER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_LOOKBACK, default=DEFAULT_LOOKBACK): vol.All(
            int, vol.Range(min=0)
        ),
        vol.Optional(CONFIG_IDLE_TIMEOUT, default=DEFAULT_IDLE_TIMEOUT): vol.All(
            int, vol.Range(min=0)
        ),
        vol.Optional(CONFIG_RETAIN, default=DEFAULT_RETAIN): vol.All(
            int, vol.Range(min=1)
        ),
        vol.Optional(CONFIG_FOLDER, default=DEFAULT_FOLDER): str,
        vol.Optional(CONFIG_FILENAME_PATTERN, default=DEFAULT_FILENAME_PATTERN): str,
        vol.Optional(CONFIG_EXTENSION, default=DEFAULT_EXTENSION): str,
        vol.Optional(CONFIG_THUMBNAIL, default=DEFAULT_THUMBNAIL): THUMBNAIL_SCHEMA,
    }
)

CONFIG_NAME = "name"
CONFIG_IDENTIFIER = "identifier"
CONFIG_PUBLISH_IMAGE = "publish_image"
CONFIG_MJPEG_STREAMS = "mjpeg_streams"
CONFIG_RECORDER = "recorder"

DEFAULT_IDENTIFIER = None
DEFAULT_PUBLISH_IMAGE = False
DEFAULT_MJPEG_STREAMS: Dict[str, Any] = {}
DEFAULT_RECORDER: Dict[str, Any] = {}


BASE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_NAME): vol.All(str, vol.Length(min=1)),
        vol.Optional(CONFIG_IDENTIFIER, default=DEFAULT_IDENTIFIER): vol.Maybe(
            vol.All(str, vol.Length(min=1))
        ),
        vol.Optional(CONFIG_PUBLISH_IMAGE, default=DEFAULT_PUBLISH_IMAGE): bool,
        vol.Optional(CONFIG_MJPEG_STREAMS, default=DEFAULT_MJPEG_STREAMS): {
            vol.All(str, ensure_slug): MJPEG_STREAM_SCHEMA
        },
        vol.Optional(CONFIG_RECORDER, default=DEFAULT_RECORDER): RECORDER_SCHEMA,
    }
)

EVENT_STATUS = "{camera_identifier}/camera/status"

EVENT_STATUS_DISCONNECTED = "disconnected"

LOGGER = logging.getLogger(__name__)


@dataclass
class EventStatusData:
    """Hold information on camera status event."""

    status: str


DATA_FRAME_BYTES_TOPIC = "{camera_identifier}/camera/frame_bytes"


class AbstractCamera(ABC):
    """Represent a camera."""

    def __init__(self, vis, config):
        self._vis = vis
        self._config = config

        self._logger = logging.getLogger(__name__ + "." + self.identifier)
        self._logger.addFilter(SensitiveInformationFilter())
        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self.frame_bytes_topic = DATA_FRAME_BYTES_TOPIC.format(
            camera_identifier=self.identifier
        )

    @abstractmethod
    def start_camera(self):
        """Start camera streaming."""

    @abstractmethod
    def stop_camera(self):
        """Stop camera streaming."""

    @abstractmethod
    def start_recording(self, frame):
        """Start camera recording."""

    @abstractmethod
    def stop_recording(self):
        """Stop camera recording."""

    @property
    def name(self):
        """Return camera name."""
        return self._config[CONFIG_NAME]

    @property
    def identifier(self):
        """Return camera identifier."""
        if self._config[CONFIG_IDENTIFIER]:
            return self._config[CONFIG_IDENTIFIER]
        return slugify(self._config[CONFIG_NAME])

    @property
    @abstractmethod
    def output_fps(self):
        """Return stream output fps."""

    @property
    @abstractmethod
    def resolution(self) -> Tuple[int, int]:
        """Return stream resolution."""

    @property
    @abstractmethod
    def is_recording(self):
        """Return recording status."""


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
            cv2.cvtColor(decoded_frame, cv2.COLOR_YUV2RGB_NV21, shm_frame_rgb_numpy)

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
