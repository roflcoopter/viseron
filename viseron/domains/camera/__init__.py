"""Camera domain."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from threading import Timer
from typing import TYPE_CHECKING

import cv2
import imutils
import voluptuous as vol

from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.helpers.validators import CoerceNoneToDict, Slug

from .const import (
    CONFIG_EXTENSION,
    CONFIG_FILENAME_PATTERN,
    CONFIG_FOLDER,
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
    CONFIG_RECORDER,
    CONFIG_RETAIN,
    CONFIG_SAVE_TO_DISK,
    CONFIG_THUMBNAIL,
    DEFAULT_EXTENSION,
    DEFAULT_FILENAME_PATTERN,
    DEFAULT_FOLDER,
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
    DEFAULT_NAME,
    DEFAULT_RECORDER,
    DEFAULT_RETAIN,
    DEFAULT_SAVE_TO_DISK,
    DEFAULT_THUMBNAIL,
    DESC_EXTENSION,
    DESC_FILENAME_PATTERN,
    DESC_FILENAME_PATTERN_THUMBNAIL,
    DESC_FOLDER,
    DESC_IDLE_TIMEOUT,
    DESC_LOOKBACK,
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
    DESC_RECORDER,
    DESC_RETAIN,
    DESC_SAVE_TO_DISK,
    DESC_THUMBNAIL,
    EVENT_STATUS,
    EVENT_STATUS_CONNECTED,
    EVENT_STATUS_DISCONNECTED,
)
from .entity.binary_sensor import ConnectionStatusBinarySensor
from .entity.toggle import CameraConnectionToggle
from .shared_frames import SharedFrames

if TYPE_CHECKING:
    from viseron.domains.object_detector.detected_object import DetectedObject

    from .recorder import AbstractRecorder
    from .shared_frames import SharedFrame


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
        vol.Optional(
            CONFIG_FILENAME_PATTERN,
            default=DEFAULT_FILENAME_PATTERN,
            description=DESC_FILENAME_PATTERN_THUMBNAIL,
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
            CONFIG_RETAIN, default=DEFAULT_RETAIN, description=DESC_RETAIN
        ): vol.All(int, vol.Range(min=1)),
        vol.Optional(
            CONFIG_FOLDER, default=DEFAULT_FOLDER, description=DESC_FOLDER
        ): str,
        vol.Optional(
            CONFIG_FILENAME_PATTERN,
            default=DEFAULT_FILENAME_PATTERN,
            description=DESC_FILENAME_PATTERN,
        ): str,
        vol.Optional(
            CONFIG_EXTENSION, default=DEFAULT_EXTENSION, description=DESC_EXTENSION
        ): str,
        vol.Optional(
            CONFIG_THUMBNAIL, default=DEFAULT_THUMBNAIL, description=DESC_THUMBNAIL
        ): vol.All(CoerceNoneToDict(), THUMBNAIL_SCHEMA),
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
    }
)

LOGGER = logging.getLogger(__name__)


@dataclass
class EventStatusData:
    """Hold information on camera status event."""

    status: str


DATA_FRAME_BYTES_TOPIC = "{camera_identifier}/camera/frame_bytes"


class AbstractCamera(ABC):
    """Represent a camera."""

    def __init__(self, vis, component, config, identifier):
        self._vis = vis
        self._config = config
        self._identifier = identifier

        self._logger = logging.getLogger(f"{self.__module__}.{self.identifier}")

        self._connected: bool = False
        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self.current_frame: SharedFrame = None
        self.shared_frames = SharedFrames()
        self.frame_bytes_topic = DATA_FRAME_BYTES_TOPIC.format(
            camera_identifier=self.identifier
        )

        self._clear_cache_timer = None
        vis.add_entity(component, ConnectionStatusBinarySensor(vis, self))
        vis.add_entity(component, CameraConnectionToggle(vis, self))

    def as_dict(self):
        """Return camera information as dict."""
        return {
            "identifier": self.identifier,
            "name": self.name,
            "width": self.resolution[0],
            "height": self.resolution[1],
            "recordings": self.recorder,
        }

    @abstractmethod
    def start_camera(self):
        """Start camera streaming."""

    @abstractmethod
    def stop_camera(self):
        """Stop camera streaming."""

    @abstractmethod
    def start_recorder(
        self, shared_frame: SharedFrame, objects_in_fov: list[DetectedObject] | None
    ):
        """Start camera recorder."""

    @abstractmethod
    def stop_recorder(self):
        """Stop camera recorder."""

    @property
    def name(self):
        """Return camera name."""
        return (
            self._config[CONFIG_NAME] if self._config[CONFIG_NAME] else self.identifier
        )

    @property
    def identifier(self) -> str:
        """Return camera identifier."""
        return self._identifier

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
    def resolution(self) -> tuple[int, int]:
        """Return stream resolution."""

    @property
    @abstractmethod
    def extension(self) -> str:
        """Return recording file extension."""

    @property
    @abstractmethod
    def recorder(self) -> AbstractRecorder:
        """Return recorder."""

    @property
    @abstractmethod
    def is_recording(self):
        """Return recording status."""

    @property
    @abstractmethod
    def is_on(self):
        """Return if camera is on.

        Not the same as self.connected below.
        A camera can be on (or armed) while still being disconnected, eg during
        network outages.
        """

    @property
    def connected(self) -> bool:
        """Return if connected to camera."""
        return self._connected

    @connected.setter
    def connected(self, connected):
        if connected == self._connected:
            return

        self._connected = connected
        self._vis.dispatch_event(
            EVENT_STATUS.format(camera_identifier=self.identifier),
            EventStatusData(
                status=EVENT_STATUS_CONNECTED
                if connected
                else EVENT_STATUS_DISCONNECTED
            ),
        )

    @staticmethod
    def _clear_snapshot_cache(clear_cache):
        """Clear snapshot cache."""
        clear_cache()

    @lru_cache(maxsize=2)
    def get_snapshot(
        self,
        current_frame: SharedFrame,
        width=None,
        height=None,
    ):
        """Return current frame as jpg bytes.

        current_frame is passed in instead of taken from self.current_frame to allow
        the use of lru_cache
        """
        if self._clear_cache_timer:
            self._clear_cache_timer.cancel()

        decoded_frame = self.shared_frames.get_decoded_frame_rgb(current_frame)
        if width and height:
            decoded_frame = cv2.resize(
                decoded_frame, (width, height), interpolation=cv2.INTER_AREA
            )
        elif width or height:
            decoded_frame = imutils.resize(decoded_frame, width, height)

        ret, jpg = cv2.imencode(
            ".jpg", decoded_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100]
        )

        # Start a timer to clear the cache after some time.
        # This is done to avoid storing a frame in memory after its no longer valid
        self._clear_cache_timer = Timer(
            self.output_fps * 2,
            self._clear_snapshot_cache,
            (self.get_snapshot.cache_clear,),
        )
        self._clear_cache_timer.start()

        if ret:
            return ret, jpg.tobytes()
        return ret, False

    def delete_recording(self, date=None, recording=None):
        """Delete recording(s)."""
        return self.recorder.delete_recording(date, recording)
