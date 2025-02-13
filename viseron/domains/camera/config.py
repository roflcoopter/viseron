"""Camera domain config."""
import voluptuous as vol

from viseron.components.storage.config import STORAGE_SCHEMA, TIER_SCHEMA_BASE
from viseron.components.storage.const import (
    CONFIG_CONTINUOUS,
    CONFIG_EVENTS,
    DEFAULT_CONTINUOUS,
    DEFAULT_EVENTS,
    DESC_CONTINUOUS,
    DESC_EVENTS,
)
from viseron.helpers.validators import CoerceNoneToDict, Deprecated, Maybe, Slug

from .const import (
    AUTHENTICATION_BASIC,
    AUTHENTICATION_DIGEST,
    CONFIG_AUTHENTICATION,
    CONFIG_CONTINUOUS_RECORDING,
    CONFIG_CREATE_EVENT_CLIP,
    CONFIG_EXTENSION,
    CONFIG_FILENAME_PATTERN,
    CONFIG_FOLDER,
    CONFIG_IDLE_TIMEOUT,
    CONFIG_LOOKBACK,
    CONFIG_MAX_RECORDING_TIME,
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
    CONFIG_PASSWORD,
    CONFIG_RECORDER,
    CONFIG_REFRESH_INTERVAL,
    CONFIG_RETAIN,
    CONFIG_SAVE_TO_DISK,
    CONFIG_STILL_IMAGE,
    CONFIG_STILL_IMAGE_HEIGHT,
    CONFIG_STILL_IMAGE_WIDTH,
    CONFIG_STORAGE,
    CONFIG_THUMBNAIL,
    CONFIG_URL,
    CONFIG_USERNAME,
    DEFAULT_AUTHENTICATION,
    DEFAULT_CONTINUOUS_RECORDING,
    DEFAULT_CREATE_EVENT_CLIP,
    DEFAULT_FILENAME_PATTERN,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_LOOKBACK,
    DEFAULT_MAX_RECORDING_TIME,
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
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_RECORDER,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_SAVE_TO_DISK,
    DEFAULT_STILL_IMAGE,
    DEFAULT_STILL_IMAGE_HEIGHT,
    DEFAULT_STILL_IMAGE_WIDTH,
    DEFAULT_STORAGE,
    DEFAULT_THUMBNAIL,
    DEFAULT_URL,
    DEFAULT_USERNAME,
    DEPRECATED_EXTENSION,
    DEPRECATED_FILENAME_PATTERN_THUMBNAIL,
    DEPRECATED_FOLDER,
    DEPRECATED_RETAIN,
    DESC_AUTHENTICATION,
    DESC_CONTINUOUS_RECORDING,
    DESC_CREATE_EVENT_CLIP,
    DESC_EXTENSION,
    DESC_FILENAME_PATTERN,
    DESC_FILENAME_PATTERN_THUMBNAIL,
    DESC_FOLDER,
    DESC_IDLE_TIMEOUT,
    DESC_LOOKBACK,
    DESC_MAX_RECORDING_TIME,
    DESC_MJPEG_DRAW_MOTION,
    DESC_MJPEG_DRAW_MOTION_MASK,
    DESC_MJPEG_DRAW_OBJECT_MASK,
    DESC_MJPEG_DRAW_OBJECTS,
    DESC_MJPEG_DRAW_ZONES,
    DESC_MJPEG_HEIGHT,
    DESC_MJPEG_MIRROR,
    DESC_MJPEG_ROTATE,
    DESC_MJPEG_STREAM,
    DESC_MJPEG_STREAMS,
    DESC_MJPEG_WIDTH,
    DESC_NAME,
    DESC_PASSWORD,
    DESC_RECORDER,
    DESC_REFRESH_INTERVAL,
    DESC_RETAIN,
    DESC_SAVE_TO_DISK,
    DESC_STILL_IMAGE,
    DESC_STILL_IMAGE_HEIGHT,
    DESC_STILL_IMAGE_WIDTH,
    DESC_STORAGE,
    DESC_THUMBNAIL,
    DESC_URL,
    DESC_USERNAME,
    INCLUSION_GROUP_AUTHENTICATION,
    WARNING_EXTENSION,
    WARNING_FILENAME_PATTERN_THUMBNAIL,
    WARNING_FOLDER,
    WARNING_RETAIN,
)

MJPEG_STREAM_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_MJPEG_WIDTH,
            default=DEFAULT_MJPEG_WIDTH,
            description=DESC_MJPEG_WIDTH,
        ): vol.Coerce(int),
        vol.Optional(
            CONFIG_MJPEG_HEIGHT,
            default=DEFAULT_MJPEG_HEIGHT,
            description=DESC_MJPEG_HEIGHT,
        ): vol.Coerce(int),
        vol.Optional(
            CONFIG_MJPEG_DRAW_OBJECTS,
            default=DEFAULT_MJPEG_DRAW_OBJECTS,
            description=DESC_MJPEG_DRAW_OBJECTS,
        ): vol.Coerce(bool),
        vol.Optional(
            CONFIG_MJPEG_DRAW_MOTION,
            default=DEFAULT_MJPEG_DRAW_MOTION,
            description=DESC_MJPEG_DRAW_MOTION,
        ): vol.Coerce(bool),
        vol.Optional(
            CONFIG_MJPEG_DRAW_MOTION_MASK,
            default=DEFAULT_MJPEG_DRAW_MOTION_MASK,
            description=DESC_MJPEG_DRAW_MOTION_MASK,
        ): vol.Coerce(bool),
        vol.Optional(
            CONFIG_MJPEG_DRAW_OBJECT_MASK,
            default=DEFAULT_MJPEG_DRAW_OBJECT_MASK,
            description=DESC_MJPEG_DRAW_OBJECT_MASK,
        ): vol.Coerce(bool),
        vol.Optional(
            CONFIG_MJPEG_DRAW_ZONES,
            default=DEFAULT_MJPEG_DRAW_ZONES,
            description=DESC_MJPEG_DRAW_ZONES,
        ): vol.Coerce(bool),
        vol.Optional(
            CONFIG_MJPEG_ROTATE,
            default=DEFAULT_MJPEG_ROTATE,
            description=DESC_MJPEG_ROTATE,
        ): vol.Coerce(int),
        vol.Optional(
            CONFIG_MJPEG_MIRROR,
            default=DEFAULT_MJPEG_MIRROR,
            description=DESC_MJPEG_MIRROR,
        ): vol.Coerce(bool),
    }
)

THUMBNAIL_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_SAVE_TO_DISK,
            default=DEFAULT_SAVE_TO_DISK,
            description=DESC_SAVE_TO_DISK,
        ): bool,
        Deprecated(
            CONFIG_FILENAME_PATTERN,
            description=DESC_FILENAME_PATTERN_THUMBNAIL,
            message=DEPRECATED_FILENAME_PATTERN_THUMBNAIL,
            warning=WARNING_FILENAME_PATTERN_THUMBNAIL,
        ): str,
    }
)


RECORDER_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_LOOKBACK, default=DEFAULT_LOOKBACK, description=DESC_LOOKBACK
        ): vol.All(int, vol.Range(min=0)),
        vol.Optional(
            CONFIG_IDLE_TIMEOUT,
            default=DEFAULT_IDLE_TIMEOUT,
            description=DESC_IDLE_TIMEOUT,
        ): vol.All(int, vol.Range(min=0)),
        vol.Optional(
            CONFIG_MAX_RECORDING_TIME,
            default=DEFAULT_MAX_RECORDING_TIME,
            description=DESC_MAX_RECORDING_TIME,
        ): vol.All(int, vol.Range(min=0)),
        Deprecated(
            CONFIG_RETAIN,
            description=DESC_RETAIN,
            message=DEPRECATED_RETAIN,
            warning=WARNING_RETAIN,
        ): vol.All(int, vol.Range(min=1)),
        Deprecated(
            CONFIG_FOLDER,
            description=DESC_FOLDER,
            message=DEPRECATED_FOLDER,
            warning=WARNING_FOLDER,
        ): str,
        vol.Optional(
            CONFIG_FILENAME_PATTERN,
            default=DEFAULT_FILENAME_PATTERN,
            description=DESC_FILENAME_PATTERN,
        ): str,
        Deprecated(
            CONFIG_EXTENSION,
            description=DESC_EXTENSION,
            message=DEPRECATED_EXTENSION,
            warning=WARNING_EXTENSION,
        ): str,
        vol.Optional(
            CONFIG_THUMBNAIL, default=DEFAULT_THUMBNAIL, description=DESC_THUMBNAIL
        ): vol.All(CoerceNoneToDict(), THUMBNAIL_SCHEMA),
        vol.Optional(
            CONFIG_CONTINUOUS,
            default=DEFAULT_CONTINUOUS,
            description=DESC_CONTINUOUS,
        ): Maybe(TIER_SCHEMA_BASE),
        vol.Optional(
            CONFIG_EVENTS,
            default=DEFAULT_EVENTS,
            description=DESC_EVENTS,
        ): Maybe(TIER_SCHEMA_BASE),
        vol.Optional(
            CONFIG_CREATE_EVENT_CLIP,
            default=DEFAULT_CREATE_EVENT_CLIP,
            description=DESC_CREATE_EVENT_CLIP,
        ): bool,
        vol.Optional(
            CONFIG_CONTINUOUS_RECORDING,
            default=DEFAULT_CONTINUOUS_RECORDING,
            description=DESC_CONTINUOUS_RECORDING,
        ): bool,
    }
)

STILL_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_URL,
            default=DEFAULT_URL,
            description=DESC_URL,
        ): Maybe(str),
        vol.Inclusive(
            CONFIG_USERNAME,
            INCLUSION_GROUP_AUTHENTICATION,
            default=DEFAULT_USERNAME,
            description=DESC_USERNAME,
        ): Maybe(str),
        vol.Inclusive(
            CONFIG_PASSWORD,
            INCLUSION_GROUP_AUTHENTICATION,
            default=DEFAULT_PASSWORD,
            description=DESC_PASSWORD,
        ): Maybe(str),
        vol.Optional(
            CONFIG_AUTHENTICATION,
            default=DEFAULT_AUTHENTICATION,
            description=DESC_AUTHENTICATION,
        ): Maybe(vol.In([AUTHENTICATION_BASIC, AUTHENTICATION_DIGEST])),
        vol.Optional(
            CONFIG_REFRESH_INTERVAL,
            default=DEFAULT_REFRESH_INTERVAL,
            description=DESC_REFRESH_INTERVAL,
        ): vol.All(int, vol.Range(min=1)),
        vol.Optional(
            CONFIG_STILL_IMAGE_WIDTH,
            default=DEFAULT_STILL_IMAGE_WIDTH,
            description=DESC_STILL_IMAGE_WIDTH,
        ): Maybe(vol.All(int, vol.Range(min=1))),
        vol.Optional(
            CONFIG_STILL_IMAGE_HEIGHT,
            default=DEFAULT_STILL_IMAGE_HEIGHT,
            description=DESC_STILL_IMAGE_HEIGHT,
        ): Maybe(vol.All(int, vol.Range(min=1))),
    }
)

BASE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_NAME, default=DEFAULT_NAME, description=DESC_NAME): vol.All(
            str, vol.Length(min=1)
        ),
        vol.Optional(
            CONFIG_MJPEG_STREAMS,
            default=DEFAULT_MJPEG_STREAMS,
            description=DESC_MJPEG_STREAMS,
        ): vol.All(
            CoerceNoneToDict(),
            {Slug(description=DESC_MJPEG_STREAM): MJPEG_STREAM_SCHEMA},
        ),
        vol.Optional(
            CONFIG_RECORDER, default=DEFAULT_RECORDER, description=DESC_RECORDER
        ): vol.All(CoerceNoneToDict(), RECORDER_SCHEMA),
        vol.Optional(
            CONFIG_STILL_IMAGE,
            default=DEFAULT_STILL_IMAGE,
            description=DESC_STILL_IMAGE,
        ): vol.All(CoerceNoneToDict(), STILL_IMAGE_SCHEMA),
        vol.Optional(
            CONFIG_STORAGE,
            default=DEFAULT_STORAGE,
            description=DESC_STORAGE,
        ): Maybe(STORAGE_SCHEMA),
    }
)
