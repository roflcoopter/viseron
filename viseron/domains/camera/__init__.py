"""Camera domain."""
from __future__ import annotations

import logging
import os
import secrets
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from threading import Event, Timer
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import cv2
import imutils
from sqlalchemy import or_, select
from typing_extensions import assert_never

from viseron.components import DomainToSetup
from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.components.storage.config import validate_tiers
from viseron.components.storage.const import (
    COMPONENT as STORAGE_COMPONENT,
    TIER_CATEGORY_RECORDER,
    TIER_CATEGORY_SNAPSHOTS,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_THUMBNAILS,
)
from viseron.components.storage.models import Files
from viseron.components.webserver.const import COMPONENT as WEBSERVER_COMPONENT
from viseron.const import TEMP_DIR
from viseron.domains.camera.entity.sensor import CamerAccessTokenSensor
from viseron.domains.camera.fragmenter import Fragmenter
from viseron.domains.camera.recorder import FailedCameraRecorder
from viseron.events import EventData, EventEmptyData
from viseron.helpers import (
    annotate_frame,
    calculate_absolute_coords,
    create_directory,
    draw_objects,
    escape_string,
    utcnow,
    zoom_boundingbox,
)
from viseron.helpers.logs import SensitiveInformationFilter
from viseron.types import SnapshotDomain

from .const import (
    CONFIG_MJPEG_STREAMS,
    CONFIG_NAME,
    CONFIG_PASSWORD,
    CONFIG_REFRESH_INTERVAL,
    CONFIG_STILL_IMAGE,
    CONFIG_STILL_IMAGE_HEIGHT,
    CONFIG_STILL_IMAGE_WIDTH,
    CONFIG_STORAGE,
    CONFIG_URL,
    EVENT_CAMERA_STARTED,
    EVENT_CAMERA_STATUS,
    EVENT_CAMERA_STATUS_CONNECTED,
    EVENT_CAMERA_STATUS_DISCONNECTED,
    EVENT_CAMERA_STILL_IMAGE_AVAILABLE,
    EVENT_CAMERA_STOPPED,
    UPDATE_TOKEN_INTERVAL_MINUTES,
    VIDEO_CONTAINER,
)
from .entity.binary_sensor import (
    ConnectionStatusBinarySensor,
    StillImageAvailableBinarySensor,
)
from .entity.toggle import CameraConnectionToggle
from .shared_frames import SharedFrames

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.nvr.nvr import FrameIntervalCalculator
    from viseron.components.storage import Storage
    from viseron.components.storage.models import TriggerTypes
    from viseron.components.webserver import Webserver
    from viseron.domains.object_detector.detected_object import DetectedObject

    from .recorder import AbstractRecorder
    from .shared_frames import SharedFrame


LOGGER = logging.getLogger(__name__)


@dataclass
class EventCameraStatusData(EventData):
    """Hold information on camera status event."""

    status: str


@dataclass
class EventCameraStillImageAvailable(EventData):
    """Hold information on camera still image available event."""

    available: bool


DATA_FRAME_BYTES_TOPIC = "{camera_identifier}/camera/frame_bytes"


class AbstractCamera(ABC):
    """Represent a camera."""

    def __init__(self, vis: Viseron, component: str, config, identifier: str) -> None:
        self._vis = vis
        self._config = config
        self._identifier = identifier

        self._logger = logging.getLogger(f"{self.__module__}.{self.identifier}")

        if self._config[CONFIG_STORAGE]:
            validate_tiers(self._config)

        self._connected: bool = False
        self._still_image_available: bool = False
        self.stopped = Event()
        self.stopped.set()
        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self.current_frame: SharedFrame | None = None
        self.shared_frames = SharedFrames(vis)
        self.frame_bytes_topic = DATA_FRAME_BYTES_TOPIC.format(
            camera_identifier=self.identifier
        )
        self.access_tokens: deque = deque([], 2)
        self.access_tokens.append(self.generate_token())

        self._clear_cache_timer: Timer | None = None
        vis.add_entity(component, ConnectionStatusBinarySensor(vis, self))
        vis.add_entity(component, StillImageAvailableBinarySensor(vis, self))
        vis.add_entity(component, CameraConnectionToggle(vis, self))
        self._access_token_entity = vis.add_entity(
            component, CamerAccessTokenSensor(vis, self)
        )

        self.update_token()
        self._vis.background_scheduler.add_job(
            self.update_token, "interval", minutes=UPDATE_TOKEN_INTERVAL_MINUTES
        )

        self._storage: Storage = vis.data[STORAGE_COMPONENT]
        self.event_clips_folder: str = self._storage.get_event_clips_path(self)
        self.segments_folder: str = self._storage.get_segments_path(self)
        self.thumbnails_folder: str = self._storage.get_thumbnails_path(self)
        self.temp_segments_folder: str = TEMP_DIR + self.segments_folder
        self.snapshots_object_folder: str = self._storage.get_snapshots_path(
            self, SnapshotDomain.OBJECT_DETECTOR
        )
        self.snapshots_face_folder: str = self._storage.get_snapshots_path(
            self, SnapshotDomain.FACE_RECOGNITION
        )
        self.snapshots_license_plate_folder: str = self._storage.get_snapshots_path(
            self, SnapshotDomain.LICENSE_PLATE_RECOGNITION
        )
        self.snapshots_motion_folder: str = self._storage.get_snapshots_path(
            self, SnapshotDomain.MOTION_DETECTOR
        )

        self.fragmenter: Fragmenter = Fragmenter(vis, self)
        if self.config[CONFIG_PASSWORD]:
            SensitiveInformationFilter.add_sensitive_string(
                self.config[CONFIG_PASSWORD]
            )
            SensitiveInformationFilter.add_sensitive_string(
                escape_string(self._config[CONFIG_PASSWORD])
            )

        if self.still_image_configured:
            self._logger.debug("Still image is configured, setting availability.")
            self.still_image_available = True

    def as_dict(self) -> dict[str, Any]:
        """Return camera information as dict."""
        return {
            "identifier": self.identifier,
            "name": self.name,
            "width": self.resolution[0],
            "height": self.resolution[1],
            "access_token": self.access_token,
            "still_image": {
                "refresh_interval": self.still_image[CONFIG_REFRESH_INTERVAL],
                "available": self.still_image_available,
                "width": self.still_image_width,
                "height": self.still_image_height,
            },
            "is_on": self.is_on,
            "connected": self.connected,
        }

    def generate_token(self):
        """Generate a new access token."""
        return secrets.token_hex(64)

    def update_token(self) -> None:
        """Update access token."""
        old_access_token = None
        if len(self.access_tokens) == 2:
            old_access_token = self.access_tokens[0]

        new_access_token = self.generate_token()
        SensitiveInformationFilter.add_sensitive_string(new_access_token)

        self.access_tokens.append(new_access_token)

        if old_access_token:
            SensitiveInformationFilter.remove_sensitive_string(
                old_access_token,
            )
        self._access_token_entity.set_state()

    def calculate_output_fps(self, scanners: list[FrameIntervalCalculator]) -> None:
        """Calculate the camera output fps based on registered frame scanners."""
        highest_fps = max(scanner.scan_fps for scanner in scanners)
        self.output_fps = highest_fps

    def start_camera(self):
        """Start camera streaming."""
        self.stopped.clear()
        self._start_camera()
        self._vis.dispatch_event(
            EVENT_CAMERA_STARTED.format(camera_identifier=self.identifier),
            EventEmptyData(),
        )

    @abstractmethod
    def _start_camera(self):
        """Start camera streaming."""

    def stop_camera(self):
        """Stop camera streaming."""
        self._stop_camera()
        self.still_image_available = self.still_image_configured
        self.stopped.set()
        self._vis.dispatch_event(
            EVENT_CAMERA_STOPPED.format(camera_identifier=self.identifier),
            EventEmptyData(),
        )
        if self.is_recording:
            self.stop_recorder()
        self.current_frame = None

    @abstractmethod
    def _stop_camera(self):
        """Stop camera streaming."""

    @abstractmethod
    def start_recorder(
        self,
        shared_frame: SharedFrame,
        objects_in_fov: list[DetectedObject] | None,
        trigger_type: TriggerTypes,
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
    def extension(self) -> str:
        """Return recording file extension."""
        return VIDEO_CONTAINER

    @property
    @abstractmethod
    def recorder(self) -> AbstractRecorder:
        """Return recorder."""

    @property
    @abstractmethod
    def is_recording(self):
        """Return recording status."""

    @property
    def is_on(self):
        """Return if camera is on.

        Not the same as self.connected below.
        A camera can be on (or armed) while still being disconnected, eg during
        network outages.
        """
        return not self.stopped.is_set()

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
            EVENT_CAMERA_STATUS.format(camera_identifier=self.identifier),
            EventCameraStatusData(
                status=EVENT_CAMERA_STATUS_CONNECTED
                if connected
                else EVENT_CAMERA_STATUS_DISCONNECTED
            ),
        )

    @property
    def still_image(self) -> dict[str, Any]:
        """Return still image config."""
        return self._config[CONFIG_STILL_IMAGE]

    @property
    def still_image_configured(self) -> bool:
        """Return if still image is configured."""
        return bool(self._config[CONFIG_STILL_IMAGE][CONFIG_URL])

    @property
    def still_image_width(self) -> int:
        """Return still image width."""
        if self.still_image[CONFIG_STILL_IMAGE_WIDTH]:
            return self.still_image[CONFIG_STILL_IMAGE_WIDTH]
        return self.resolution[0]

    @property
    def still_image_height(self) -> int:
        """Return still image height."""
        if self.still_image[CONFIG_STILL_IMAGE_HEIGHT]:
            return self.still_image[CONFIG_STILL_IMAGE_HEIGHT]
        return self.resolution[1]

    @property
    def still_image_available(self) -> bool:
        """Return if still image is available."""
        return self._still_image_available

    @still_image_available.setter
    def still_image_available(self, available: bool) -> None:
        """Set still image availability."""
        if available == self._still_image_available:
            return

        self._still_image_available = available
        self._vis.dispatch_event(
            EVENT_CAMERA_STILL_IMAGE_AVAILABLE.format(
                camera_identifier=self.identifier
            ),
            EventCameraStillImageAvailable(available=available),
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

    def _get_folder(self, domain: SnapshotDomain) -> str:
        if domain is SnapshotDomain.OBJECT_DETECTOR:
            return self.snapshots_object_folder
        if domain is SnapshotDomain.FACE_RECOGNITION:
            return self.snapshots_face_folder
        if domain is SnapshotDomain.LICENSE_PLATE_RECOGNITION:
            return self.snapshots_license_plate_folder
        if domain == SnapshotDomain.MOTION_DETECTOR:
            return self.snapshots_motion_folder
        assert_never(domain)

    def save_snapshot(
        self,
        shared_frame: SharedFrame,
        domain: SnapshotDomain,
        zoom_coordinates: tuple[float, float, float, float] | None = None,
        detected_object: DetectedObject | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        text: str | None = None,
        subfolder: str | None = None,
    ) -> str:
        """Save snapshot to disk."""
        decoded_frame = self.shared_frames.get_decoded_frame_rgb(shared_frame)
        snapshot_frame = decoded_frame

        if detected_object:
            draw_objects(snapshot_frame, [detected_object])
        if bbox:
            annotate_frame(
                snapshot_frame,
                calculate_absolute_coords(bbox, self.resolution),
                text or None,
            )

        if zoom_coordinates:
            snapshot_frame = zoom_boundingbox(
                decoded_frame,
                calculate_absolute_coords(zoom_coordinates, self.resolution),
                crop_correction_factor=1.2,
            )

        folder = self._get_folder(domain)

        if subfolder:
            folder = os.path.join(folder, subfolder)

        filename = f"{utcnow().strftime('%Y-%m-%d-%H-%M-%S-')}{str(uuid4())}.jpg"

        path = os.path.join(folder, filename)
        self._logger.debug(f"Saving snapshot to {path}")
        create_directory(folder)
        cv2.imwrite(path, snapshot_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        return path


class FailedCamera:
    """Failed camera.

    This class is instantiated when a camera fails to initialize.
    It allows us to expose the camera to the frontend, so that the user can
    see that the camera has failed.
    It also gives access to the cameras recordings.
    """

    def __init__(self, vis: Viseron, domain_to_setup: DomainToSetup) -> None:
        """Initialize failed camera."""
        # Local import to avoid circular import
        # pylint: disable=import-outside-toplevel
        from viseron.components.storage.tier_handler import add_file_handler

        self._vis = vis
        self._domain_to_setup = domain_to_setup
        self._config: dict[str, Any] = domain_to_setup.config[
            domain_to_setup.identifier
        ]

        self._storage: Storage = vis.data[STORAGE_COMPONENT]
        self._webserver: Webserver = vis.data[WEBSERVER_COMPONENT]
        self._recorder = FailedCameraRecorder(vis, self._config, self)

        # Try to guess the path to the camera recordings
        with self._storage.get_session() as session:
            recorder_dir_stmt = (
                select(Files)
                .distinct(Files.directory)
                .where(Files.camera_identifier == self.identifier)
                .where(Files.category == TIER_CATEGORY_RECORDER)
                .where(Files.subcategory == TIER_SUBCATEGORY_SEGMENTS)
                .order_by(Files.directory, Files.created_at.desc())
            )
            for file in session.execute(recorder_dir_stmt).scalars():
                add_file_handler(
                    vis,
                    self._webserver,
                    file.directory,
                    rf"{file.directory}/(.*.m4s$)",
                    self,
                    TIER_CATEGORY_RECORDER,
                    TIER_SUBCATEGORY_SEGMENTS,
                )
                add_file_handler(
                    vis,
                    self._webserver,
                    file.directory,
                    rf"{file.directory}/(.*.mp4$)",
                    self,
                    TIER_CATEGORY_RECORDER,
                    TIER_SUBCATEGORY_SEGMENTS,
                )

        # Try to guess the path to the camera snapshots and thumbnails
        with self._storage.get_session() as session:
            jpg_dir_stmt = (
                select(Files)
                .distinct(Files.directory)
                .where(Files.camera_identifier == self.identifier)
                .where(
                    or_(
                        Files.category == TIER_CATEGORY_SNAPSHOTS,
                        Files.subcategory == TIER_SUBCATEGORY_THUMBNAILS,
                    )
                )
                .order_by(Files.directory, Files.created_at.desc())
            )
            for file in session.execute(jpg_dir_stmt).scalars():
                add_file_handler(
                    vis,
                    self._webserver,
                    file.directory,
                    rf"{file.directory}/(.*.jpg$)",
                    self,
                    file.category,
                    file.subcategory,
                )

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
    def config(self) -> dict[str, Any]:
        """Return camera config."""
        return self._config

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
        return VIDEO_CONTAINER

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
