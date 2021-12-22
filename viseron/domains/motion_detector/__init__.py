"""Motion detector domain."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from queue import Empty, Queue
from typing import TYPE_CHECKING

import cv2
import numpy as np
import voluptuous as vol

from viseron.components.data_stream import COMPONENT as DATA_STREAM_COMPONENT
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.helpers import generate_mask
from viseron.helpers.schemas import COORDINATES_SCHEMA
from viseron.watchdog.thread_watchdog import RestartableThread

from .binary_sensor import MotionDetectionBinarySensor
from .const import (
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
    DEFAULT_AREA,
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_MASK,
    DEFAULT_MAX_RECORDER_KEEPALIVE,
    DEFAULT_RECORDER_KEEPALIVE,
    DEFAULT_TRIGGER_RECORDER,
    DEFAULT_WIDTH,
    EVENT_MOTION_DETECTED,
)

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.camera.shared_frames import SharedFrame

    from .contours import Contours


CAMERA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_TRIGGER_RECORDER, default=DEFAULT_TRIGGER_RECORDER): bool,
        vol.Optional(
            CONFIG_RECORDER_KEEPALIVE, default=DEFAULT_RECORDER_KEEPALIVE
        ): bool,
        vol.Optional(
            CONFIG_MAX_RECORDER_KEEPALIVE, default=DEFAULT_MAX_RECORDER_KEEPALIVE
        ): vol.All(int, vol.Range(min=0)),
    }
)

BASE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_CAMERAS): {str: CAMERA_SCHEMA},
    }
)


@dataclass
class EventMotionDetected:
    """Hold information on motion event."""

    camera_identifier: str
    motion_detected: bool
    shared_frame: SharedFrame | None = None
    motion_contours: Contours | None = None


class AbstractMotionDetector(ABC):
    """Abstract motion detector."""

    def __init__(self, vis, component, config, camera_identifier):
        self._vis = vis
        self._config = config

        self._camera: AbstractCamera = vis.get_registered_camera(camera_identifier)
        self._logger = logging.getLogger(f"{self.__module__}.{camera_identifier}")
        self._motion_detected = False

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

    def _motion_detected_setter(
        self,
        motion_detected,
        shared_frame: SharedFrame = None,
        contours: Contours = None,
    ):
        if self._motion_detected == motion_detected:
            return

        self._motion_detected = motion_detected
        self._logger.debug("Motion detected" if motion_detected else "Motion stopped")
        self._vis.dispatch_event(
            EVENT_MOTION_DETECTED.format(camera_identifier=self._camera.identifier),
            EventMotionDetected(
                camera_identifier=self._camera.identifier,
                shared_frame=shared_frame,
                motion_detected=True,
                motion_contours=contours,
            ),
        )


CAMERA_SCHEMA_SCANNER = CAMERA_SCHEMA.extend(
    {
        vol.Optional(CONFIG_FPS, default=DEFAULT_FPS): vol.All(
            vol.Any(float, int), vol.Coerce(float), vol.Range(min=0.0)
        ),
        vol.Optional(CONFIG_AREA, default=DEFAULT_AREA): vol.All(
            vol.Any(
                vol.All(
                    float,
                    vol.Range(min=0.0, max=1.0),
                ),
                1,
                0,
            ),
            vol.Coerce(float),
        ),
        vol.Optional(CONFIG_WIDTH, default=DEFAULT_WIDTH): int,
        vol.Optional(CONFIG_HEIGHT, default=DEFAULT_HEIGHT): int,
        vol.Optional(CONFIG_MASK, default=DEFAULT_MASK): [
            {vol.Required(CONFIG_COORDINATES): COORDINATES_SCHEMA}
        ],
    }
)

BASE_CONFIG_SCHEMA_SCANNER = vol.Schema(
    {
        vol.Required(CONFIG_CAMERAS): {str: CAMERA_SCHEMA_SCANNER},
    }
)


class AbstractMotionDetectorScanner(AbstractMotionDetector):
    """Abstract motion detector that works by scanning frames."""

    def __init__(self, vis, component, config, camera_identifier, color_format="gray"):
        super().__init__(vis, component, config, camera_identifier)

        self._get_frame_function = getattr(self, f"_get_decoded_frame_{color_format}")

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
                    vis.get_registered_camera(camera_identifier).resolution,
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
        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)

    @abstractmethod
    def preprocess(self, frame):
        """Perform preprocessing of frame before running detection."""

    def _apply_mask(self, frame):
        """Apply motion mask to frame."""
        frame[self._mask_image] = [0]
        return frame

    def _filter_motion(self, shared_frame: SharedFrame, contours: Contours):
        """Filter motion."""
        self._logger.debug(
            "Max motion area: {max_area}".format(max_area=contours.max_area)
        )
        self._motion_detected_setter(
            bool(
                contours.max_area
                > self._config[CONFIG_CAMERAS][self._camera.identifier][CONFIG_AREA]
            ),
            shared_frame,
            contours,
        )

    def _get_decoded_frame_rgb(self, shared_frame):
        """Return frame in rgb format."""
        return self._camera.shared_frames.get_decoded_frame_rgb(shared_frame)

    def _get_decoded_frame_gray(self, shared_frame):
        """Return frame in gray format."""
        return self._camera.shared_frames.get_decoded_frame_gray(shared_frame)

    def _motion_detection(self):
        """Perform object detection and publish the results."""
        while not self._kill_received:
            try:
                shared_frame: SharedFrame = self.motion_detection_queue.get(timeout=1)
            except Empty:
                continue

            decoded_frame = self._get_frame_function(shared_frame)
            preprocessed_frame = self.preprocess(decoded_frame)
            if self._mask:
                preprocessed_frame = self._apply_mask(preprocessed_frame)

            contours = self.return_motion(preprocessed_frame)
            self._filter_motion(shared_frame, contours)
            self._vis.data[DATA_STREAM_COMPONENT].publish_data(
                DATA_MOTION_DETECTOR_RESULT.format(
                    camera_identifier=shared_frame.camera_identifier
                ),
                contours,
            )
        self._logger.debug("Motion detection thread stopped")

    @abstractmethod
    def return_motion(self, frame):
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

    def stop(self):
        """Stop object detector."""
        self._kill_received = True
        self._motion_detection_thread.join()
