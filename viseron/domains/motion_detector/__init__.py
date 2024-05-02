"""Motion detector domain."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np
import voluptuous as vol
from sqlalchemy import insert, update

from viseron.components.data_stream import COMPONENT as DATA_STREAM_COMPONENT
from viseron.components.nvr.const import EVENT_SCAN_FRAMES, MOTION_DETECTOR
from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT
from viseron.components.storage.models import Motion, MotionContours
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.domains.motion_detector.binary_sensor import MotionDetectionBinarySensor
from viseron.domains.motion_detector.const import (
    CONFIG_AREA,
    CONFIG_CAMERAS,
    CONFIG_COORDINATES,
    CONFIG_FPS,
    CONFIG_HEIGHT,
    CONFIG_MASK,
    CONFIG_MAX_RECORDER_KEEPALIVE,
    CONFIG_RECORDER_KEEPALIVE,
    CONFIG_TRIGGER_RECORDER,
    CONFIG_WIDTH,
    DATA_MOTION_DETECTOR_RESULT,
    DATA_MOTION_DETECTOR_SCAN,
    DEFAULT_AREA,
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_MASK,
    DEFAULT_MAX_RECORDER_KEEPALIVE,
    DEFAULT_RECORDER_KEEPALIVE,
    DEFAULT_TRIGGER_RECORDER,
    DEFAULT_WIDTH,
    DESC_AREA,
    DESC_CAMERAS,
    DESC_COORDINATES,
    DESC_FPS,
    DESC_HEIGHT,
    DESC_MASK,
    DESC_MAX_RECORDER_KEEPALIVE,
    DESC_RECORDER_KEEPALIVE,
    DESC_TRIGGER_RECORDER,
    DESC_WIDTH,
    EVENT_MOTION_DETECTED,
)
from viseron.events import EventData
from viseron.helpers import generate_mask, utcnow
from viseron.helpers.schemas import (
    COORDINATES_SCHEMA,
    FLOAT_MIN_ZERO,
    FLOAT_MIN_ZERO_MAX_ONE,
)
from viseron.helpers.validators import CameraIdentifier
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.components.data_stream import DataStream
    from viseron.components.nvr.nvr import EventScanFrames
    from viseron.components.storage import Storage
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.camera.shared_frames import SharedFrame

    from .contours import Contours


CAMERA_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_TRIGGER_RECORDER,
            default=DEFAULT_TRIGGER_RECORDER,
            description=DESC_TRIGGER_RECORDER,
        ): bool,
        vol.Optional(
            CONFIG_RECORDER_KEEPALIVE,
            default=DEFAULT_RECORDER_KEEPALIVE,
            description=DESC_RECORDER_KEEPALIVE,
        ): bool,
        vol.Optional(
            CONFIG_MAX_RECORDER_KEEPALIVE,
            default=DEFAULT_MAX_RECORDER_KEEPALIVE,
            description=DESC_MAX_RECORDER_KEEPALIVE,
        ): vol.All(int, vol.Range(min=0)),
    }
)

BASE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
            CameraIdentifier(): CAMERA_SCHEMA
        },
    }
)


@dataclass
class EventMotionDetected(EventData):
    """Hold information on motion event."""

    camera_identifier: str
    motion_detected: bool
    shared_frame: SharedFrame | None = None
    motion_contours: Contours | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return event data as dict."""
        return {
            "camera_identifier": self.camera_identifier,
            "motion_detected": self.motion_detected,
            "motion_contours": self.motion_contours,
        }


class AbstractMotionDetector(ABC):
    """Abstract motion detector."""

    def __init__(
        self,
        vis: Viseron,
        component: str,
        config: dict[Any, Any],
        camera_identifier: str,
    ) -> None:
        self._vis = vis
        self._config = config
        self._storage: Storage = vis.data[STORAGE_COMPONENT]

        self._camera: AbstractCamera = vis.get_registered_domain(
            CAMERA_DOMAIN, camera_identifier
        )
        self._logger = logging.getLogger(f"{self.__module__}.{camera_identifier}")
        self._motion_detected = False
        self._motion_contours: Contours | None = None
        self._motion_id: int | None = None

        vis.add_entity(component, MotionDetectionBinarySensor(vis, self, self._camera))

    @property
    def trigger_recorder(self):
        """Return if detected motion should start recorder."""
        return self._config[CONFIG_CAMERAS][self._camera.identifier][
            CONFIG_TRIGGER_RECORDER
        ]

    @property
    def recorder_keepalive(self):
        """Return if motion should keep a recording going."""
        return self._config[CONFIG_CAMERAS][self._camera.identifier][
            CONFIG_RECORDER_KEEPALIVE
        ]

    @property
    def max_recorder_keepalive(self):
        """Return max seconds that motion is allowed to keep a recording going."""
        return self._config[CONFIG_CAMERAS][self._camera.identifier][
            CONFIG_MAX_RECORDER_KEEPALIVE
        ]

    @property
    def motion_detected(self):
        """Return if motion is detected."""
        return self._motion_detected

    @property
    def motion_contours(self):
        """Return motion contours."""
        return self._motion_contours

    def _insert_motion(self) -> None:
        """Insert motion event into database."""
        with self._storage.get_session() as session:
            stmt = (
                insert(Motion)
                .values(
                    camera_identifier=self._camera.identifier,
                    start_time=utcnow(),
                    end_time=None,
                )
                .returning(Motion.id)
            )
            result = session.execute(stmt).scalars()
            self._motion_id = result.one()
            if self._motion_contours:
                for contour in self._motion_contours.contours:
                    stmt2 = insert(MotionContours).values(
                        motion_id=self._motion_id,
                        contour=contour,
                    )
                    session.execute(stmt2)

            session.commit()

    def _update_motion(self) -> None:
        """Update motion event to set end_time."""
        with self._storage.get_session() as session:
            stmt = (
                update(Motion)
                .values(
                    end_time=utcnow(),
                )
                .where(Motion.id == self._motion_id)
            )
            session.execute(stmt)
            session.commit()

    def _motion_detected_setter(
        self,
        motion_detected,
        shared_frame: SharedFrame | None = None,
        contours: Contours | None = None,
    ) -> None:
        self._motion_contours = contours
        if self._motion_detected == motion_detected:
            return

        if self._motion_id is None:
            self._insert_motion()
        else:
            self._update_motion()
            self._motion_id = None

        self._motion_detected = motion_detected
        self._logger.debug("Motion detected" if motion_detected else "Motion stopped")
        self._vis.dispatch_event(
            EVENT_MOTION_DETECTED.format(camera_identifier=self._camera.identifier),
            EventMotionDetected(
                camera_identifier=self._camera.identifier,
                shared_frame=shared_frame,
                motion_detected=motion_detected,
                motion_contours=contours,
            ),
        )


CAMERA_SCHEMA_SCANNER = CAMERA_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_FPS, default=DEFAULT_FPS, description=DESC_FPS
        ): FLOAT_MIN_ZERO,
        vol.Optional(
            CONFIG_AREA, default=DEFAULT_AREA, description=DESC_AREA
        ): FLOAT_MIN_ZERO_MAX_ONE,
        vol.Optional(CONFIG_WIDTH, default=DEFAULT_WIDTH, description=DESC_WIDTH): int,
        vol.Optional(
            CONFIG_HEIGHT, default=DEFAULT_HEIGHT, description=DESC_HEIGHT
        ): int,
        vol.Optional(CONFIG_MASK, default=DEFAULT_MASK, description=DESC_MASK): [
            {
                vol.Required(
                    CONFIG_COORDINATES, description=DESC_COORDINATES
                ): COORDINATES_SCHEMA
            }
        ],
    }
)


class AbstractMotionDetectorScanner(AbstractMotionDetector):
    """Abstract motion detector that works by scanning frames."""

    def __init__(
        self, vis: Viseron, component, config, camera_identifier, color_format="gray"
    ) -> None:
        super().__init__(vis, component, config, camera_identifier)

        self._get_frame_function: Callable[[SharedFrame], np.ndarray] = getattr(
            self, f"_get_decoded_frame_{color_format}"
        )
        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]

        self._resolution = (
            config[CONFIG_CAMERAS][camera_identifier][CONFIG_WIDTH],
            config[CONFIG_CAMERAS][camera_identifier][CONFIG_HEIGHT],
        )

        self._mask = None
        if config[CONFIG_CAMERAS][camera_identifier][CONFIG_MASK]:
            self._logger.debug("Creating mask")
            self._mask = generate_mask(
                config[CONFIG_CAMERAS][camera_identifier][CONFIG_MASK]
            )

            # Scale mask to fit resized frame
            scaled_mask = []
            for point_list in self._mask:
                rel_mask = np.divide(
                    (point_list),
                    self._camera.resolution,
                )
                scaled_mask.append(
                    np.multiply(rel_mask, self._resolution).astype("int32")
                )

            mask = np.zeros(
                (
                    self._resolution[0],
                    self._resolution[1],
                    3,
                ),
                np.uint8,
            )
            mask[:] = 255

            cv2.fillPoly(mask, pts=scaled_mask, color=(0, 0, 0))
            self._mask_image = np.where(mask[:, :, 0] == [0])

        self._kill_received = False
        self.motion_detection_queue: Queue[SharedFrame] = Queue(maxsize=1)
        self._motion_detection_thread = RestartableThread(
            target=self._motion_detection,
            name=f"{camera_identifier}.motion_detection",
            register=True,
            daemon=True,
        )
        self._motion_detection_thread.start()
        topic = DATA_MOTION_DETECTOR_SCAN.format(camera_identifier=camera_identifier)
        self._data_stream.subscribe_data(
            data_topic=topic,
            callback=self.motion_detection_queue,
        )

        vis.listen_event(
            EVENT_SCAN_FRAMES.format(
                camera_identifier=camera_identifier, scanner_name=MOTION_DETECTOR
            ),
            self.handle_stop_scan,
        )

        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)

    @abstractmethod
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Perform preprocessing of frame before running detection."""

    def _apply_mask(self, frame: np.ndarray) -> np.ndarray:
        """Apply motion mask to frame."""
        frame[self._mask_image] = [0]
        return frame

    def _filter_motion(self, shared_frame: SharedFrame, contours: Contours) -> None:
        """Filter motion."""
        self._logger.debug("Max motion area: %s", contours.max_area)
        self._motion_detected_setter(
            bool(
                contours.max_area
                > self._config[CONFIG_CAMERAS][self._camera.identifier][CONFIG_AREA]
            ),
            shared_frame,
            contours,
        )

    def _get_decoded_frame_rgb(self, shared_frame) -> np.ndarray:
        """Return frame in rgb format."""
        return self._camera.shared_frames.get_decoded_frame_rgb(shared_frame)

    def _get_decoded_frame_gray(self, shared_frame) -> np.ndarray:
        """Return frame in gray format."""
        return self._camera.shared_frames.get_decoded_frame_gray(shared_frame)

    def _motion_detection(self) -> None:
        """Perform motion detection and publish the results."""
        while not self._kill_received:
            try:
                shared_frame: SharedFrame = self.motion_detection_queue.get(timeout=1)
            except Empty:
                continue

            decoded_frame = self._get_frame_function(shared_frame).copy()
            preprocessed_frame = self.preprocess(decoded_frame)
            if self._mask:
                preprocessed_frame = self._apply_mask(preprocessed_frame)

            contours = self.return_motion(preprocessed_frame)
            self._filter_motion(shared_frame, contours)
            self._data_stream.publish_data(
                DATA_MOTION_DETECTOR_RESULT.format(
                    camera_identifier=shared_frame.camera_identifier
                ),
                contours,
            )
        self._logger.debug("Motion detection thread stopped")

    @abstractmethod
    def return_motion(self, frame) -> Contours:
        """Perform motion detection."""

    @property
    def fps(self):
        """Return motion detector fps."""
        return self._config[CONFIG_CAMERAS][self._camera.identifier][CONFIG_FPS]

    @property
    def mask(self):
        """Return motion detector mask."""
        return self._mask

    @property
    def area(self):
        """Return motion detector area."""
        return self._config[CONFIG_CAMERAS][self._camera.identifier][CONFIG_AREA]

    def handle_stop_scan(self, event_data: Event[EventScanFrames]) -> None:
        """Handle event when stopping frame scans."""
        if event_data.data.scan is False:
            self._motion_detected_setter(False, None, None)

    def stop(self) -> None:
        """Stop motion detector."""
        self._kill_received = True
        self._motion_detection_thread.join()
