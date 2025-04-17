"""Object detector domain."""
from __future__ import annotations

import logging
import time
from abc import abstractmethod
from collections import deque
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from sqlalchemy import insert

from viseron.components.data_stream import COMPONENT as DATA_STREAM_COMPONENT
from viseron.components.nvr.const import EVENT_SCAN_FRAMES, OBJECT_DETECTOR
from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT
from viseron.components.storage.models import Objects
from viseron.const import INSERT, VISERON_SIGNAL_SHUTDOWN
from viseron.domains import AbstractDomain
from viseron.domains.camera.const import (
    DOMAIN as CAMERA_DOMAIN,
    EVENT_CAMERA_EVENT_DB_OPERATION,
)
from viseron.domains.camera.events import EventCameraEventData
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.domains.motion_detector.const import DOMAIN as MOTION_DETECTOR_DOMAIN
from viseron.exceptions import DomainNotRegisteredError
from viseron.helpers import apply_mask, generate_mask, generate_mask_image
from viseron.helpers.filter import Filter
from viseron.helpers.schemas import (
    COORDINATES_SCHEMA,
    FLOAT_MIN_ZERO,
    FLOAT_MIN_ZERO_MAX_ONE,
)
from viseron.helpers.validators import CameraIdentifier, Deprecated
from viseron.types import SnapshotDomain
from viseron.watchdog.thread_watchdog import RestartableThread

from .binary_sensor import (
    ObjectDetectedBinarySensorFoV,
    ObjectDetectedBinarySensorFoVLabel,
)
from .const import (
    CONFIG_CAMERAS,
    CONFIG_COORDINATES,
    CONFIG_FPS,
    CONFIG_LABEL_CONFIDENCE,
    CONFIG_LABEL_HEIGHT_MAX,
    CONFIG_LABEL_HEIGHT_MIN,
    CONFIG_LABEL_LABEL,
    CONFIG_LABEL_REQUIRE_MOTION,
    CONFIG_LABEL_STORE,
    CONFIG_LABEL_STORE_INTERVAL,
    CONFIG_LABEL_TRIGGER_EVENT_RECORDING,
    CONFIG_LABEL_TRIGGER_RECORDER,
    CONFIG_LABEL_WIDTH_MAX,
    CONFIG_LABEL_WIDTH_MIN,
    CONFIG_LABELS,
    CONFIG_LOG_ALL_OBJECTS,
    CONFIG_MASK,
    CONFIG_MAX_FRAME_AGE,
    CONFIG_SCAN_ON_MOTION_ONLY,
    CONFIG_ZONE_NAME,
    CONFIG_ZONES,
    DATA_OBJECT_DETECTOR_RESULT,
    DATA_OBJECT_DETECTOR_SCAN,
    DEFAULT_FPS,
    DEFAULT_LABEL_CONFIDENCE,
    DEFAULT_LABEL_HEIGHT_MAX,
    DEFAULT_LABEL_HEIGHT_MIN,
    DEFAULT_LABEL_REQUIRE_MOTION,
    DEFAULT_LABEL_STORE,
    DEFAULT_LABEL_STORE_INTERVAL,
    DEFAULT_LABEL_TRIGGER_EVENT_RECORDING,
    DEFAULT_LABEL_WIDTH_MAX,
    DEFAULT_LABEL_WIDTH_MIN,
    DEFAULT_LABELS,
    DEFAULT_LOG_ALL_OBJECTS,
    DEFAULT_MASK,
    DEFAULT_MAX_FRAME_AGE,
    DEFAULT_SCAN_ON_MOTION_ONLY,
    DEFAULT_ZONES,
    DEPRECATED_LABEL_TRIGGER_RECORDER,
    DESC_CAMERAS,
    DESC_COORDINATES,
    DESC_FPS,
    DESC_LABEL_CONFIDENCE,
    DESC_LABEL_HEIGHT_MAX,
    DESC_LABEL_HEIGHT_MIN,
    DESC_LABEL_LABEL,
    DESC_LABEL_REQUIRE_MOTION,
    DESC_LABEL_STORE,
    DESC_LABEL_STORE_INTERVAL,
    DESC_LABEL_TRIGGER_EVENT_RECORDING,
    DESC_LABEL_TRIGGER_RECORDER,
    DESC_LABEL_WIDTH_MAX,
    DESC_LABEL_WIDTH_MIN,
    DESC_LABELS,
    DESC_LOG_ALL_OBJECTS,
    DESC_MASK,
    DESC_MAX_FRAME_AGE,
    DESC_SCAN_ON_MOTION_ONLY,
    DESC_ZONE_NAME,
    DESC_ZONES,
    DOMAIN,
    EVENT_OBJECTS_IN_FOV,
    WARNING_LABEL_TRIGGER_RECORDER,
)
from .detected_object import DetectedObject, EventDetectedObjectsData
from .sensor import ObjectDetectorFPSSensor
from .zone import Zone

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.components.nvr.nvr import EventScanFrames
    from viseron.components.storage import Storage
    from viseron.domains.camera import AbstractCamera


def ensure_min_max(label: dict) -> dict:
    """Ensure min values are not larger than max values."""
    if label["height_min"] >= label["height_max"]:
        raise vol.Invalid("height_min may not be larger or equal to height_max")
    if label["width_min"] >= label["width_max"]:
        raise vol.Invalid("width_min may not be larger or equal to width_max")
    return label


LABEL_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(
                CONFIG_LABEL_LABEL,
                description=DESC_LABEL_LABEL,
            ): str,
            vol.Optional(
                CONFIG_LABEL_CONFIDENCE,
                default=DEFAULT_LABEL_CONFIDENCE,
                description=DESC_LABEL_CONFIDENCE,
            ): FLOAT_MIN_ZERO_MAX_ONE,
            vol.Optional(
                CONFIG_LABEL_HEIGHT_MIN,
                default=DEFAULT_LABEL_HEIGHT_MIN,
                description=DESC_LABEL_HEIGHT_MIN,
            ): FLOAT_MIN_ZERO_MAX_ONE,
            vol.Optional(
                CONFIG_LABEL_HEIGHT_MAX,
                default=DEFAULT_LABEL_HEIGHT_MAX,
                description=DESC_LABEL_HEIGHT_MAX,
            ): FLOAT_MIN_ZERO_MAX_ONE,
            vol.Optional(
                CONFIG_LABEL_WIDTH_MIN,
                default=DEFAULT_LABEL_WIDTH_MIN,
                description=DESC_LABEL_WIDTH_MIN,
            ): FLOAT_MIN_ZERO_MAX_ONE,
            vol.Optional(
                CONFIG_LABEL_WIDTH_MAX,
                default=DEFAULT_LABEL_WIDTH_MAX,
                description=DESC_LABEL_WIDTH_MAX,
            ): FLOAT_MIN_ZERO_MAX_ONE,
            Deprecated(
                CONFIG_LABEL_TRIGGER_RECORDER,
                description=DESC_LABEL_TRIGGER_RECORDER,
                message=DEPRECATED_LABEL_TRIGGER_RECORDER,
                warning=WARNING_LABEL_TRIGGER_RECORDER,
            ): bool,
            vol.Optional(
                CONFIG_LABEL_TRIGGER_EVENT_RECORDING,
                default=DEFAULT_LABEL_TRIGGER_EVENT_RECORDING,
                description=DESC_LABEL_TRIGGER_EVENT_RECORDING,
            ): bool,
            vol.Optional(
                CONFIG_LABEL_STORE,
                default=DEFAULT_LABEL_STORE,
                description=DESC_LABEL_STORE,
            ): bool,
            vol.Optional(
                CONFIG_LABEL_STORE_INTERVAL,
                default=DEFAULT_LABEL_STORE_INTERVAL,
                description=DESC_LABEL_STORE_INTERVAL,
            ): int,
            vol.Optional(
                CONFIG_LABEL_REQUIRE_MOTION,
                default=DEFAULT_LABEL_REQUIRE_MOTION,
                description=DESC_LABEL_REQUIRE_MOTION,
            ): bool,
        },
        ensure_min_max,
    )
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_ZONE_NAME, description=DESC_ZONE_NAME): str,
        vol.Required(
            CONFIG_COORDINATES, description=DESC_COORDINATES
        ): COORDINATES_SCHEMA,
        vol.Optional(CONFIG_LABELS, default=DEFAULT_LABELS, description=DESC_LABELS): [
            LABEL_SCHEMA
        ],
    }
)

CAMERA_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_FPS, default=DEFAULT_FPS, description=DESC_FPS
        ): FLOAT_MIN_ZERO,
        vol.Optional(
            CONFIG_SCAN_ON_MOTION_ONLY,
            default=DEFAULT_SCAN_ON_MOTION_ONLY,
            description=DESC_SCAN_ON_MOTION_ONLY,
        ): bool,
        vol.Optional(CONFIG_LABELS, default=DEFAULT_LABELS, description=DESC_LABELS): [
            LABEL_SCHEMA
        ],
        vol.Optional(
            CONFIG_MAX_FRAME_AGE,
            default=DEFAULT_MAX_FRAME_AGE,
            description=DESC_MAX_FRAME_AGE,
        ): FLOAT_MIN_ZERO,
        vol.Optional(
            CONFIG_LOG_ALL_OBJECTS,
            default=DEFAULT_LOG_ALL_OBJECTS,
            description=DESC_LOG_ALL_OBJECTS,
        ): bool,
        vol.Optional(CONFIG_MASK, default=DEFAULT_MASK, description=DESC_MASK): [
            {
                vol.Required(
                    CONFIG_COORDINATES, description=DESC_COORDINATES
                ): COORDINATES_SCHEMA
            }
        ],
        vol.Optional(CONFIG_ZONES, default=DEFAULT_ZONES, description=DESC_ZONES): [
            ZONE_SCHEMA
        ],
    },
)


BASE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
            CameraIdentifier(): CAMERA_SCHEMA
        },
    }
)


class AbstractObjectDetector(AbstractDomain):
    """Abstract Object Detector."""

    def __init__(
        self,
        vis: Viseron,
        component: str,
        config: dict[Any, Any],
        camera_identifier: str,
    ) -> None:
        self._vis = vis
        self._storage: Storage = vis.data[STORAGE_COMPONENT]
        self._config = config
        self._camera_identifier = camera_identifier
        self._camera: AbstractCamera = vis.get_registered_domain(
            CAMERA_DOMAIN, camera_identifier
        )
        self._logger = logging.getLogger(f"{self.__module__}.{camera_identifier}")

        self._objects_in_fov: list[DetectedObject] = []
        self.object_filters: dict[str, Filter] = {}

        self._preproc_fps: deque[float] = deque(maxlen=50)
        self._inference_fps: deque[float] = deque(maxlen=50)
        self._theoretical_max_fps: deque[float] = deque(maxlen=50)

        self._mask = []
        if config[CONFIG_CAMERAS][camera_identifier][CONFIG_MASK]:
            self._mask = generate_mask(
                config[CONFIG_CAMERAS][camera_identifier][CONFIG_MASK]
            )
            self._mask_image = generate_mask_image(self._mask, self._camera.resolution)

        if config[CONFIG_CAMERAS][camera_identifier][CONFIG_LABELS]:
            for object_filter in config[CONFIG_CAMERAS][camera_identifier][
                CONFIG_LABELS
            ]:
                self.object_filters[object_filter[CONFIG_LABEL_LABEL]] = Filter(
                    self._camera.resolution,
                    object_filter,
                    self._mask,
                )
                vis.add_entity(
                    component,
                    ObjectDetectedBinarySensorFoVLabel(
                        vis, object_filter[CONFIG_LABEL_LABEL], self._camera
                    ),
                )

        self.zones: list[Zone] = []
        for zone in config[CONFIG_CAMERAS][camera_identifier][CONFIG_ZONES]:
            self.zones.append(Zone(vis, component, camera_identifier, zone, self._mask))

        if not self.zones and not self.object_filters:
            self._logger.warning(
                "No labels or zones configured. No objects will be detected"
            )

        self._min_confidence = min(
            (label.confidence for label in self.concat_labels()),
            default=1.0,
        )

        self._kill_received = False
        self.object_detection_queue: Queue[SharedFrame] = Queue(maxsize=1)
        self._object_detection_thread = RestartableThread(
            target=self._object_detection,
            name=f"{camera_identifier}.object_detection",
            register=True,
            daemon=True,
        )
        self._object_detection_thread.start()
        topic = DATA_OBJECT_DETECTOR_SCAN.format(camera_identifier=camera_identifier)
        self._vis.data[DATA_STREAM_COMPONENT].subscribe_data(
            data_topic=topic,
            callback=self.object_detection_queue,
        )

        vis.listen_event(
            EVENT_SCAN_FRAMES.format(
                camera_identifier=camera_identifier, scanner_name=OBJECT_DETECTOR
            ),
            self.handle_stop_scan,
        )

        self._scan_on_motion_only = self._config[CONFIG_CAMERAS][
            self._camera.identifier
        ][CONFIG_SCAN_ON_MOTION_ONLY]
        if self.scan_on_motion_only:
            try:
                vis.get_registered_domain(MOTION_DETECTOR_DOMAIN, camera_identifier)
            except DomainNotRegisteredError:
                self._logger.warning(
                    "scan_on_motion_only is enabled but no motion detector is "
                    "configured. Disabling scan_on_motion_only"
                )
                self._scan_on_motion_only = False

        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)
        vis.add_entity(component, ObjectDetectedBinarySensorFoV(vis, self._camera))
        vis.add_entity(component, ObjectDetectorFPSSensor(vis, self, self._camera))

    def __post_init__(self, *args, **kwargs):
        """Post init hook."""
        self._vis.register_domain(DOMAIN, self._camera_identifier, self)

    def concat_labels(self) -> list[Filter]:
        """Return a concatenated list of global filters + all filters in each zone."""
        zone_filters = []
        for zone in self.zones:
            zone_filters += list(zone.object_filters.values())

        return list(self.object_filters.values()) + zone_filters

    def filter_fov(
        self, shared_frame: SharedFrame, objects: list[DetectedObject]
    ) -> None:
        """Filter field of view."""
        objects_in_fov = []
        for obj in objects:
            if self.object_filters.get(obj.label) and self.object_filters[
                obj.label
            ].filter_object(obj):
                obj.relevant = True
                objects_in_fov.append(obj)

                if self.object_filters[obj.label].trigger_event_recording:
                    obj.trigger_event_recording = True
                self.object_filters[obj.label].should_store(obj)

        self._objects_in_fov_setter(shared_frame, objects_in_fov)
        if self._config[CONFIG_CAMERAS][self._camera.identifier][
            CONFIG_LOG_ALL_OBJECTS
        ]:
            self._logger.debug(
                "All objects: %s",
                [obj.formatted for obj in objects],
            )
        else:
            self._logger.debug(
                "Objects: %s", [obj.formatted for obj in self.objects_in_fov]
            )

    @property
    def objects_in_fov(self):
        """Return all objects in field of view."""
        return self._objects_in_fov

    def _insert_object(
        self, obj: DetectedObject, snapshot_path: str | None, zone=None
    ) -> None:
        """Insert object into database."""
        with self._storage.get_session() as session:
            stmt = insert(Objects).values(
                camera_identifier=self._camera.identifier,
                label=obj.label,
                confidence=obj.confidence,
                width=obj.rel_width,
                height=obj.rel_height,
                x1=obj.rel_x1,
                y1=obj.rel_y1,
                x2=obj.rel_x2,
                y2=obj.rel_y2,
                snapshot_path=snapshot_path,
                zone=zone,
            )
            session.execute(stmt)
            session.commit()

    def _insert_objects(
        self, shared_frame: SharedFrame, objects: list[DetectedObject]
    ) -> None:
        """Insert objects into database."""
        for obj in objects:
            if obj.store:
                snapshot_path = None
                if shared_frame:
                    snapshot_path = self._camera.save_snapshot(
                        shared_frame,
                        SnapshotDomain.OBJECT_DETECTOR,
                        (
                            obj.rel_x1,
                            obj.rel_y1,
                            obj.rel_x2,
                            obj.rel_y2,
                        ),
                        detected_object=obj,
                    )
                self._insert_object(obj, snapshot_path)
                self._vis.dispatch_event(
                    EVENT_CAMERA_EVENT_DB_OPERATION.format(
                        camera_identifier=self._camera.identifier,
                        domain=DOMAIN,
                        operation=INSERT,
                    ),
                    EventCameraEventData(
                        camera_identifier=self._camera.identifier,
                        domain=DOMAIN,
                        operation=INSERT,
                        data=obj,
                    ),
                )

    def _objects_in_fov_setter(
        self, shared_frame: SharedFrame | None, objects: list[DetectedObject]
    ) -> None:
        """Set objects in field of view."""
        if objects == self._objects_in_fov:
            return

        self._objects_in_fov = objects
        self._vis.dispatch_event(
            EVENT_OBJECTS_IN_FOV.format(camera_identifier=self._camera.identifier),
            EventDetectedObjectsData(
                camera_identifier=self._camera.identifier,
                shared_frame=shared_frame,
                objects=objects,
            ),
        )

    def filter_zones(
        self, shared_frame: SharedFrame, objects: list[DetectedObject]
    ) -> None:
        """Filter all zones."""
        for zone in self.zones:
            zone.filter_zone(shared_frame, objects)

    @abstractmethod
    def preprocess(self, frame):
        """Perform preprocessing of frame before running detection."""

    def _object_detection(self) -> None:
        """Object detection thread."""
        while not self._kill_received:
            try:
                shared_frame: SharedFrame = self.object_detection_queue.get(timeout=1)
            except Empty:
                continue

            frame_time = time.time()
            if (frame_age := frame_time - shared_frame.capture_time) > self._config[
                CONFIG_CAMERAS
            ][shared_frame.camera_identifier][CONFIG_MAX_FRAME_AGE]:
                self._logger.debug(f"Frame is {frame_age} seconds old. Discarding")
                continue

            with shared_frame:
                self._detect(shared_frame, frame_time)

        self._logger.debug("Object detection thread stopped")

    def _detect(self, shared_frame: SharedFrame, frame_time: float):
        """Perform object detection and publish data."""
        decoded_frame = self._camera.shared_frames.get_decoded_frame_rgb(shared_frame)
        if self._mask:
            apply_mask(decoded_frame, self._mask_image)
        preprocessed_frame = self.preprocess(decoded_frame)
        self._preproc_fps.append(1 / (time.time() - frame_time))

        frame_time = time.time()
        objects = self.return_objects(preprocessed_frame)
        if objects is None:
            return

        self._inference_fps.append(1 / (time.time() - frame_time))

        self.filter_fov(shared_frame, objects)
        self.filter_zones(shared_frame, objects)
        self._insert_objects(shared_frame, objects)
        self._vis.data[DATA_STREAM_COMPONENT].publish_data(
            DATA_OBJECT_DETECTOR_RESULT.format(
                camera_identifier=shared_frame.camera_identifier
            ),
            self.objects_in_fov,
        )
        self._theoretical_max_fps.append(1 / (time.time() - frame_time))

    @abstractmethod
    def return_objects(self, frame) -> list[DetectedObject] | None:
        """Perform object detection."""

    @property
    def fps(self):
        """Return object detector fps."""
        return self._config[CONFIG_CAMERAS][self._camera_identifier][CONFIG_FPS]

    @property
    def scan_on_motion_only(self):
        """Return if scanning should only be done when there is motion."""
        return self._scan_on_motion_only

    @property
    def mask(self):
        """Return object detection mask."""
        return self._mask

    @property
    def min_confidence(self) -> float:
        """Return the minimum confidence of all tracked labels."""
        return self._min_confidence

    @staticmethod
    def _avg_fps(fps_deque: deque):
        """Calculate the average fps from a deuqe of measurements."""
        if fps_deque:
            return round(sum(fps_deque) / len(fps_deque), 1)
        return 0

    @property
    def preproc_fps(self):
        """Return the image preprocessor average fps."""
        return self._avg_fps(self._preproc_fps)

    @property
    def inference_fps(self):
        """Return the detector inferenace average fps."""
        return self._avg_fps(self._inference_fps)

    @property
    def theoretical_max_fps(self):
        """Return the theoretical max average fps."""
        return self._avg_fps(self._theoretical_max_fps)

    def handle_stop_scan(self, event_data: Event[EventScanFrames]) -> None:
        """Handle event when stopping frame scans."""
        if event_data.data.scan is False:
            self._objects_in_fov_setter(None, [])
            for zone in self.zones:
                zone.objects_in_zone_setter(None, [])

    def stop(self) -> None:
        """Stop object detector."""
        self._kill_received = True
        self._object_detection_thread.join()
