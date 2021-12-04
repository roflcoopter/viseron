"""Camera domain."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Tuple

import voluptuous as vol

from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.domains.camera.shared_frames import SharedFrames
from viseron.helpers import slugify
from viseron.helpers.logs import SensitiveInformationFilter
from viseron.helpers.validators import ensure_slug

from .const import (
    CONFIG_EXTENSION,
    CONFIG_FILENAME_PATTERN,
    CONFIG_FOLDER,
    CONFIG_IDENTIFIER,
    CONFIG_IDLE_TIMEOUT,
    CONFIG_LOOKBACK,
    CONFIG_MJPEG_DRAW_MOTION,
    CONFIG_MJPEG_DRAW_MOTION_MASK,
    CONFIG_MJPEG_DRAW_OBJECT_MASK,
    CONFIG_MJPEG_DRAW_OBJECTS,
    CONFIG_MJPEG_DRAW_ZONES,
    CONFIG_MJPEG_HEIGHT,
    CONFIG_MJPEG_MIRROR,
    CONFIG_MJPEG_ROTATE,
    CONFIG_MJPEG_STREAMS,
    CONFIG_MJPEG_WIDTH,
    CONFIG_NAME,
    CONFIG_PUBLISH_IMAGE,
    CONFIG_RECORDER,
    CONFIG_RETAIN,
    CONFIG_SAVE_TO_DISK,
    CONFIG_SEND_TO_MQTT,
    CONFIG_THUMBNAIL,
    DEFAULT_EXTENSION,
    DEFAULT_FILENAME_PATTERN,
    DEFAULT_FOLDER,
    DEFAULT_IDENTIFIER,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_LOOKBACK,
    DEFAULT_MJPEG_DRAW_MOTION,
    DEFAULT_MJPEG_DRAW_MOTION_MASK,
    DEFAULT_MJPEG_DRAW_OBJECT_MASK,
    DEFAULT_MJPEG_DRAW_OBJECTS,
    DEFAULT_MJPEG_DRAW_ZONES,
    DEFAULT_MJPEG_HEIGHT,
    DEFAULT_MJPEG_MIRROR,
    DEFAULT_MJPEG_ROTATE,
    DEFAULT_MJPEG_STREAMS,
    DEFAULT_MJPEG_WIDTH,
    DEFAULT_PUBLISH_IMAGE,
    DEFAULT_RECORDER,
    DEFAULT_RETAIN,
    DEFAULT_SAVE_TO_DISK,
    DEFAULT_SEND_TO_MQTT,
    DEFAULT_THUMBNAIL,
)

if TYPE_CHECKING:
    from .recorder import AbstractRecorder

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

THUMBNAIL_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_SAVE_TO_DISK, default=DEFAULT_SAVE_TO_DISK): bool,
        vol.Optional(CONFIG_FILENAME_PATTERN, default=DEFAULT_FILENAME_PATTERN): str,
        vol.Optional(CONFIG_SEND_TO_MQTT, default=DEFAULT_SEND_TO_MQTT): bool,
    }
)


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

        self._logger = logging.getLogger(f"{self.__module__}.{self.identifier}")

        self._logger.addFilter(SensitiveInformationFilter())
        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self.shared_frames = SharedFrames()
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
    def start_recorder(self, shared_frame, objects_in_fov):
        """Start camera recorder."""

    @abstractmethod
    def stop_recorder(self):
        """Stop camera recorder."""

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
    def mjpeg_streams(self):
        """Return mjpeg streamsr."""
        return self._config[CONFIG_MJPEG_STREAMS]

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
    def recorder(self) -> AbstractRecorder:
        """Return recorder."""

    @property
    @abstractmethod
    def is_recording(self):
        """Return recording status."""
