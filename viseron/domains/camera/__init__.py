"""Camera domain."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

import voluptuous as vol

from viseron.domains.object_detector import (
    BASE_CONFIG_SCHEMA as OBJ_DET_BASE_CONFIG_SCHEMA,
    LABEL_SCHEMA,
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

CONFIG_X = "x"
CONFIG_Y = "y"

COORDINATES_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONFIG_X): int,
            vol.Required(CONFIG_Y): int,
        }
    ]
)

CONFIG_MASK = "mask"
CONFIG_COORDINATES = "coordinates"

DEFAULT_MASK: List[Dict[str, int]] = []

OBJECT_DETECTOR_SCHEMA = OBJ_DET_BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(CONFIG_MASK, default=DEFAULT_MASK): [
            {vol.Required(CONFIG_COORDINATES): COORDINATES_SCHEMA}
        ],
    }
)

CONFIG_ZONE_NAME = "name"
CONFIG_ZONE_LABELS = "labels"


ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_ZONE_NAME): str,
        vol.Required(CONFIG_COORDINATES): COORDINATES_SCHEMA,
        vol.Optional(CONFIG_ZONE_LABELS): [LABEL_SCHEMA],
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
CONFIG_OBJECT_DETECTOR = "object_detector"
CONFIG_MOTION_DETECTOR = "motion_detector"
CONFIG_ZONES = "zones"
CONFIG_PUBLISH_IMAGE = "publish_image"
CONFIG_MJPEG_STREAMS = "mjpeg_streams"
CONFIG_RECORDER = "recorder"

DEFAULT_IDENTIFIER = None
DEFAULT_OBJECT_DETECTOR: Dict[str, Any] = {}
DEFAULT_MOTION_DETECTOR: Dict[str, Any] = {}
DEFAULT_ZONES: List[Dict[str, Any]] = []
DEFAULT_PUBLISH_IMAGE = False
DEFAULT_MJPEG_STREAMS: Dict[str, Any] = {}
DEFAULT_RECORDER: Dict[str, Any] = {}


BASE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_NAME): vol.All(str, vol.Length(min=1)),
        vol.Optional(CONFIG_IDENTIFIER, default=DEFAULT_IDENTIFIER): vol.Maybe(
            vol.All(str, vol.Length(min=1))
        ),
        vol.Optional(
            CONFIG_OBJECT_DETECTOR, default=DEFAULT_OBJECT_DETECTOR
        ): OBJECT_DETECTOR_SCHEMA,
        vol.Optional(CONFIG_ZONES, default=DEFAULT_ZONES): [ZONE_SCHEMA],
        vol.Optional(CONFIG_PUBLISH_IMAGE, default=DEFAULT_PUBLISH_IMAGE): bool,
        vol.Optional(CONFIG_MJPEG_STREAMS, default=DEFAULT_MJPEG_STREAMS): {
            vol.All(str, ensure_slug): MJPEG_STREAM_SCHEMA
        },
        vol.Optional(CONFIG_RECORDER, default=DEFAULT_RECORDER): RECORDER_SCHEMA,
    }
)


class AbstractCamera(ABC):
    """Represent a camera."""

    def __init__(self, vis, config):
        self._vis = vis
        self._config = config
        self._logger = logging.getLogger(__name__ + "." + self.identifier)
        self._logger.addFilter(SensitiveInformationFilter())
        vis.data.setdefault(DOMAIN, []).append(self)

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
    def resolution(self) -> Tuple[int, int]:
        """Return stream resolution."""

    @abstractmethod
    def start_camera(self):
        """Start camera streaming."""

    @abstractmethod
    def stop_camera(self):
        """Stop camera streaming."""

    @abstractmethod
    def start_recording(self):
        """Start camera recording."""

    @abstractmethod
    def stop_recording(self):
        """Stop camera recording."""
