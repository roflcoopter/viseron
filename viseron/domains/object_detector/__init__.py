"""Object detector domain."""
from __future__ import annotations

import collections
import logging
import time
from abc import ABC, abstractmethod
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any, Deque, Dict, List

import voluptuous as vol

from viseron.components.data_stream import COMPONENT as DATA_STREAM_COMPONENT
from viseron.components.nvr.const import EVENT_SCAN_FRAMES, OBJECT_DETECTOR
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.domains.motion_detector.const import DOMAIN as MOTION_DETECTOR_DOMAIN
from viseron.exceptions import DomainNotRegisteredError
from viseron.helpers import generate_mask
from viseron.helpers.filter import Filter
from viseron.helpers.schemas import (
    COORDINATES_SCHEMA,
    FLOAT_MIN_ZERO,
    FLOAT_MIN_ZERO_MAX_ONE,
)
from viseron.helpers.validators import CameraIdentifier
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
    DEFAULT_LABEL_TRIGGER_RECORDER,
    DEFAULT_LABEL_WIDTH_MAX,
    DEFAULT_LABEL_WIDTH_MIN,
    DEFAULT_LABELS,
    DEFAULT_LOG_ALL_OBJECTS,
    DEFAULT_MASK,
    DEFAULT_MAX_FRAME_AGE,
    DEFAULT_SCAN_ON_MOTION_ONLY,
    DEFAULT_ZONES,
    DESC_CAMERAS,
    DESC_COORDINATES,
    DESC_FPS,
    DESC_LABEL_CONFIDENCE,
    DESC_LABEL_HEIGHT_MAX,
    DESC_LABEL_HEIGHT_MIN,
    DESC_LABEL_LABEL,
    DESC_LABEL_REQUIRE_MOTION,
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
    EVENT_OBJECTS_IN_FOV,
)
from .detected_object import DetectedObject, EventDetectedObjectsData
from .sensor import ObjectDetectorFPSSensor
from .zone import Zone

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.components.nvr.nvr import EventScanFrames


def ensure_min_max(label: dict) -> dict:
    """Ensure min values are not larger than max values."""
    if label["height_min"] >= label["height_max"]:
        raise vol.Invalid("height_min may not be larger or equal to height_max")
    if label["width_min"] >= label["width_max"]:
        raise vol.Invalid("width_min may not be larger or equal to width_max")
    return label


LABEL_SCHEMA = vol.Schema(
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
        vol.Optional(
            CONFIG_LABEL_TRIGGER_RECORDER,
            default=DEFAULT_LABEL_TRIGGER_RECORDER,
            description=DESC_LABEL_TRIGGER_RECORDER,
        ): bool,
        vol.Optional(
            CONFIG_LABEL_REQUIRE_MOTION,
            default=DEFAULT_LABEL_REQUIRE_MOTION,
            description=DESC_LABEL_REQUIRE_MOTION,
        ): bool,
    },
    ensure_min_max,
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


class AbstractObjectDetector(ABC):
    """Abstract Object Detector."""

    def __init__(
        self,
        vis: Viseron,
        component: str,
        config: Dict[Any, Any],
        camera_identifier: str,
    ):
        self._vis = vis
        self._config = config
        self._camera_identifier = camera_identifier
        self._camera: AbstractCamera = vis.get_registered_domain(
            CAMERA_DOMAIN, camera_identifier
        )
        self._logger = logging.getLogger(f"{self.__module__}.{camera_identifier}")

        self._objects_in_fov: List[DetectedObject] = []
        self.object_filters: Dict[str, Filter] = {}

        self._preproc_fps: Deque[float] = collections.deque(maxlen=50)
        self._inference_fps: Deque[float] = collections.deque(maxlen=50)
        self._theoretical_max_fps: Deque[float] = collections.deque(maxlen=50)

        self._mask = []
        if config[CONFIG_CAMERAS][camera_identifier][CONFIG_MASK]:
            self._mask = generate_mask(
                config[CONFIG_CAMERAS][camera_identifier][CONFIG_MASK]
            )

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

        self.zones: List[Zone] = []
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

    def concat_labels(self) -> List[Filter]:
        """Return a concatenated list of global filters + all filters in each zone."""
        zone_filters = []
        for zone in self.zones:
            zone_filters += list(zone.object_filters.values())

        return list(self.object_filters.values()) + zone_filters

    def filter_fov(self, shared_frame: SharedFrame, objects: List[DetectedObject]):
        """Filter field of view."""
        objects_in_fov = []
        for obj in objects:
            if self.object_filters.get(obj.label) and self.object_filters[
                obj.label
            ].filter_object(obj):
                obj.relevant = True
                objects_in_fov.append(obj)

                if self.object_filters[obj.label].trigger_recorder:
                    obj.trigger_recorder = True

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

    def _objects_in_fov_setter(
        self, shared_frame: SharedFrame | None, objects: List[DetectedObject]
    ):
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

    def filter_zones(self, shared_frame: SharedFrame, objects: List[DetectedObject]):
        """Filter all zones."""
        for zone in self.zones:
            zone.filter_zone(shared_frame, objects)

    @abstractmethod
    def preprocess(self, frame):
        """Perform preprocessing of frame before running detection."""

    def _object_detection(self):
        """Perform object detection and publish the results."""
        while not self._kill_received:
            try:
                shared_frame: SharedFrame = self.object_detection_queue.get(timeout=1)
                frame_time = time.time()
            except Empty:
                continue

            if (frame_age := frame_time - shared_frame.capture_time) > self._config[
                CONFIG_CAMERAS
            ][shared_frame.camera_identifier][CONFIG_MAX_FRAME_AGE]:
                self._logger.debug(f"Frame is {frame_age} seconds old. Discarding")
                continue

            decoded_frame = self._camera.shared_frames.get_decoded_frame_rgb(
                shared_frame
            )
            preprocessed_frame = self.preprocess(decoded_frame)
            self._preproc_fps.append(1 / (time.time() - frame_time))

            frame_time = time.time()
            objects = self.return_objects(preprocessed_frame)
            self._inference_fps.append(1 / (time.time() - frame_time))

            self.filter_fov(shared_frame, objects)
            self.filter_zones(shared_frame, objects)
            self._vis.data[DATA_STREAM_COMPONENT].publish_data(
                DATA_OBJECT_DETECTOR_RESULT.format(
                    camera_identifier=shared_frame.camera_identifier
                ),
                self.objects_in_fov,
            )
            self._theoretical_max_fps.append(1 / (time.time() - frame_time))
        self._logger.debug("Object detection thread stopped")

    @abstractmethod
    def return_objects(self, frame) -> List[DetectedObject]:
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
    def _avg_fps(fps_deque: collections.deque):
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

    def handle_stop_scan(self, event_data: Event[EventScanFrames]):
        """Handle event when stopping frame scans."""
        if event_data.data.scan is False:
            self._objects_in_fov_setter(None, [])
            for zone in self.zones:
                zone.objects_in_zone_setter(None, [])

    def stop(self):
        """Stop object detector."""
        self._kill_received = True
        self._object_detection_thread.join()
