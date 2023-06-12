"""Camera domain."""
from __future__ import annotations

import logging
import secrets
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from threading import Timer
from typing import TYPE_CHECKING, Any

import cv2
import imutils
import voluptuous as vol

from viseron.components import DomainToSetup
from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.domains.camera.entity.sensor import CamerAccessTokenSensor
from viseron.domains.camera.recorder import FailedCameraRecorder
from viseron.helpers.validators import CoerceNoneToDict, Deprecated, Maybe, Slug

from .const import (
    AUTHENTICATION_BASIC,
    AUTHENTICATION_DIGEST,
    CONFIG_AUTHENTICATION,
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
    CONFIG_PASSWORD,
    CONFIG_RECORDER,
    CONFIG_REFRESH_INTERVAL,
    CONFIG_RETAIN,
    CONFIG_SAVE_TO_DISK,
    CONFIG_STILL_IMAGE,
    CONFIG_THUMBNAIL,
    CONFIG_URL,
    CONFIG_USERNAME,
    DEFAULT_AUTHENTICATION,
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
    DEFAULT_PASSWORD,
    DEFAULT_RECORDER,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_SAVE_TO_DISK,
    DEFAULT_STILL_IMAGE,
    DEFAULT_THUMBNAIL,
    DEFAULT_URL,
    DEFAULT_USERNAME,
    DEPRECATED_RETAIN,
    DESC_AUTHENTICATION,
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
    DESC_PASSWORD,
    DESC_RECORDER,
    DESC_REFRESH_INTERVAL,
    DESC_RETAIN,
    DESC_SAVE_TO_DISK,
    DESC_STILL_IMAGE,
    DESC_THUMBNAIL,
    DESC_URL,
    DESC_USERNAME,
    EVENT_STATUS,
    EVENT_STATUS_CONNECTED,
    EVENT_STATUS_DISCONNECTED,
    INCLUSION_GROUP_AUTHENTICATION,
    UPDATE_TOKEN_INTERVAL_MINUTES,
)
from .entity.binary_sensor import ConnectionStatusBinarySensor
from .entity.toggle import CameraConnectionToggle
from .shared_frames import SharedFrames

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.nvr.nvr import FrameIntervalCalculator
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
        Deprecated(
            CONFIG_RETAIN,
            description=DESC_RETAIN,
            message=DEPRECATED_RETAIN,
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

    def __init__(self, vis: Viseron, component: str, config, identifier: str) -> None:
        self._vis = vis
        self._config = config
        self._identifier = identifier

        self._logger = logging.getLogger(f"{self.__module__}.{self.identifier}")

        self._connected: bool = False
        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self.current_frame: SharedFrame | None = None
        self.shared_frames = SharedFrames()
        self.frame_bytes_topic = DATA_FRAME_BYTES_TOPIC.format(
            camera_identifier=self.identifier
        )
        self.access_tokens: deque = deque([], 2)
        self.access_tokens.append(self.generate_token())

        self._clear_cache_timer: Timer | None = None
        vis.add_entity(component, ConnectionStatusBinarySensor(vis, self))
        vis.add_entity(component, CameraConnectionToggle(vis, self))
        self._access_token_entity = vis.add_entity(
            component, CamerAccessTokenSensor(vis, self)
        )

        self.update_token()
        self._vis.background_scheduler.add_job(
            self.update_token, "interval", minutes=UPDATE_TOKEN_INTERVAL_MINUTES
        )

    def as_dict(self) -> dict[str, Any]:
        """Return camera information as dict."""
        return {
            "identifier": self.identifier,
            "name": self.name,
            "width": self.resolution[0],
            "height": self.resolution[1],
            "access_token": self.access_token,
            "still_image_refresh_interval": self.still_image[CONFIG_REFRESH_INTERVAL],
        }

    def generate_token(self):
        """Generate a new access token."""
        return secrets.token_hex(64)

    def update_token(self) -> None:
        """Update access token."""
        self.access_tokens.append(self.generate_token())
        self._access_token_entity.set_state()

    def calculate_output_fps(self, scanners: list[FrameIntervalCalculator]) -> None:
        """Calculate the camera output fps based on registered frame scanners."""
        highest_fps = max(scanner.scan_fps for scanner in scanners)
        self.output_fps = highest_fps

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
        """Return mjpeg streams."""
        return self._config[CONFIG_MJPEG_STREAMS]

    @property
    def access_token(self) -> str:
        """Return access token."""
        return self.access_tokens[-1]

    @property
    def still_image(self) -> dict[str, Any]:
        """Return still image config."""
        return self._config[CONFIG_STILL_IMAGE]

    @property
    @abstractmethod
    def output_fps(self):
        """Return stream output fps."""

    @output_fps.setter
    def output_fps(self, fps) -> None:
        """Set stream output fps."""

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
    def connected(self, connected) -> None:
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

    @property
    def config(self) -> dict[str, Any]:
        """Return camera config."""
        return self._config

    @staticmethod
    def _clear_snapshot_cache(clear_cache) -> None:
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


class FailedCamera:
    """Failed camera.

    This class is instantiated when a camera fails to initialize.
    It allows us to expose the camera to the frontend, so that the user can
    see that the camera has failed.
    It also gives access to the cameras recordings.
    """

    def __init__(self, vis: Viseron, domain_to_setup: DomainToSetup) -> None:
        """Initialize failed camera."""
        self._vis = vis
        self._domain_to_setup = domain_to_setup
        self._config: dict[str, Any] = domain_to_setup.config[
            domain_to_setup.identifier
        ]

        self._recorder = FailedCameraRecorder(vis, self._config, self)

    def as_dict(self):
        """Return camera as dict."""
        return {
            "name": self.name,
            "identifier": self.identifier,
            "width": self.width,
            "height": self.height,
            "error": self.error,
            "retrying": self.retrying,
            "failed": True,
        }

    @property
    def name(self):
        """Return camera name."""
        return self._config.get(CONFIG_NAME, self._domain_to_setup.identifier)

    @property
    def identifier(self) -> str:
        """Return camera identifier."""
        return self._domain_to_setup.identifier

    @property
    def width(self) -> int:
        """Return width."""
        return 1920

    @property
    def height(self) -> int:
        """Return height."""
        return 1080

    @property
    def extension(self) -> str:
        """Return recording file extension."""
        return self._config.get(CONFIG_RECORDER, {}).get(
            CONFIG_EXTENSION, DEFAULT_EXTENSION
        )

    @property
    def error(self):
        """Return error."""
        return self._domain_to_setup.error

    @property
    def retrying(self):
        """Return retrying."""
        return self._domain_to_setup.retrying

    @property
    def recorder(self) -> FailedCameraRecorder:
        """Return recorder."""
        return self._recorder


def setup_failed(vis: Viseron, domain_to_setup: DomainToSetup):
    """Handle failed setup."""
    return FailedCamera(vis, domain_to_setup)
