"""NVR component."""

import logging
import threading
from queue import Empty, Queue
from typing import Dict, List

import voluptuous as vol

from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import DOMAIN as CAMERA_DOMAIN, SharedFrame, SharedFrames
from viseron.domains.object_detector import LABEL_SCHEMA
from viseron.domains.object_detector.const import (
    DATA_OBJECT_DETECTOR_RESULT,
    DATA_OBJECT_DETECTOR_SCAN,
)
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.helpers.schemas import COORDINATES_SCHEMA
from viseron.helpers.validators import ensure_slug
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    COMPONENT,
    CONFIG_COORDINATES,
    CONFIG_ZONE_LABELS,
    CONFIG_ZONE_NAME,
    CONFIG_ZONES,
    DEFAULT_ZONES,
)
from .zone import Zone

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.All(str, ensure_slug): vol.Maybe({vol.Extra: object}),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_ZONE_NAME): str,
        vol.Required(CONFIG_COORDINATES): COORDINATES_SCHEMA,
        vol.Optional(CONFIG_ZONE_LABELS): [LABEL_SCHEMA],
    }
)


NVR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_ZONES, default=DEFAULT_ZONES): [ZONE_SCHEMA],
    }
)


OBJECT_DETECTOR = "object_detector"
MOTION_DETECTOR = "motion_detector"


def validate_nvr_config(config, camera_identifier):
    """Validate the config of an NVR entry."""
    try:
        return NVR_SCHEMA(config)
    except vol.Invalid as ex:
        LOGGER.exception(f"Error setting up nvr for camera {camera_identifier}: {ex}")
        return None
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Unknown error calling %s CONFIG_SCHEMA", camera_identifier)
        return None
    return True


def setup(vis, config):
    """Set up the nvr component."""
    config = config[COMPONENT]
    for camera_identifier in config.keys():
        if config[camera_identifier] is None:
            config[camera_identifier] = {}
        if validated_config := validate_nvr_config(
            config[camera_identifier], camera_identifier
        ):
            nvr = NVR(vis, validated_config, camera_identifier)
            vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, nvr.stop)

    return True


class FrameIntervalCalculator:
    """Mark frames for scanning."""

    def __init__(
        self, vis, name, logger, output_fps, scan_fps, topic_scan, topic_result
    ):
        self._topic_scan = topic_scan
        if scan_fps > output_fps:
            logger.warning(
                f"FPS for {name} is too high, " f"highest possible FPS is {output_fps}"
            )
            scan_fps = output_fps
        self._scan_interval = round(output_fps / scan_fps)

        self.scan = threading.Event()
        self._frame_number = 0
        self.result_queue = Queue(maxsize=10)

        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self._data_stream.subscribe_data(topic_result, self.result_queue)

    def check_scan_interval(self, shared_frame: SharedFrame):
        """Check if frame should be marked for scanning."""
        if self.scan.is_set():
            if self._frame_number % self._scan_interval == 0:
                self._frame_number = 1
                self._data_stream.publish_data(self._topic_scan, shared_frame)
                return True
            self._frame_number += 1
        else:
            self._frame_number = 0
        return False


DATA_MOTION_DETECTOR_SCAN = "motion_detector/{camera_identifier}/scan"
DATA_MOTION_DETECTOR_RESULT = "motion_detector/{camera_identifier}/result"


class NVR:
    """NVR class that orchestrates all handling of camera streams."""

    def __init__(self, vis, config: dict, camera_identifier: str):
        vis.data.setdefault(COMPONENT, {})[camera_identifier] = self
        self._vis = vis
        self._config = config
        self._camera = vis.data[CAMERA_DOMAIN][camera_identifier]

        self.setup_loggers()
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.debug(f"Initializing NVR for camera {self._camera.name}")

        self._kill_received = False
        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self._shared_frames = SharedFrames()

        self._frame_scanners = {}
        self._current_frame_scanners: Dict[str, FrameIntervalCalculator] = {}

        self._motion_detector = config.get(MOTION_DETECTOR, None)
        if self._motion_detector:
            self._frame_scanners[MOTION_DETECTOR] = FrameIntervalCalculator(
                vis,
                MOTION_DETECTOR,
                self._logger,
                self._camera.output_fps,
                config[MOTION_DETECTOR],
                DATA_MOTION_DETECTOR_SCAN.format(
                    camera_identifier=self._camera.identifier
                ),
                DATA_MOTION_DETECTOR_RESULT.format(
                    camera_identifier=self._camera.identifier
                ),
            )
        else:
            self._logger.info("Motion detector is disabled")

        _object_detector = self.get_object_detector()
        self._object_detector = _object_detector
        if self._object_detector:
            self._frame_scanners[OBJECT_DETECTOR] = FrameIntervalCalculator(
                vis,
                OBJECT_DETECTOR,
                self._logger,
                self._camera.output_fps,
                self._object_detector.fps,
                DATA_OBJECT_DETECTOR_SCAN.format(
                    camera_identifier=self._camera.identifier
                ),
                DATA_OBJECT_DETECTOR_RESULT.format(
                    camera_identifier=self._camera.identifier
                ),
            )
        else:
            self._logger.info("Object detector is disabled")

        if (
            self._motion_detector
            # and config[CONFIG_MOTION_DETECTOR][CONFIG_TRIGGER_DETECTOR]
        ):
            self._frame_scanners[MOTION_DETECTOR].scan.set()
            if self._object_detector:
                self._frame_scanners[OBJECT_DETECTOR].scan.clear()
        else:
            if self._object_detector:
                self._frame_scanners[OBJECT_DETECTOR].scan.set()
            if self._motion_detector:
                self._frame_scanners[MOTION_DETECTOR].scan.clear()

        self._zones: List[Zone] = []
        for zone in config[CONFIG_ZONES]:
            self._zones.append(Zone(vis, camera_identifier, config, zone))

        self._frame_queue: "Queue[bytes]" = Queue(maxsize=100)
        self._data_stream.subscribe_data(
            self._camera.frame_bytes_topic, self._frame_queue
        )
        RestartableThread(
            name=str(self),
            target=self.run,
            stop_target=self.stop,
            daemon=False,
            register=True,
        ).start()

        self._camera.start_camera()
        self._logger.debug(f"NVR for camera {self._camera.name} initialized")

    def setup_loggers(self):
        """Set up custom log names and levels."""
        self._logger = logging.getLogger(__name__ + "." + self._camera.identifier)
        self._motion_logger = logging.getLogger(
            __name__ + "." + self._camera.identifier + ".motion"
        )

    def get_object_detector(self):
        """Get object detector topic."""
        return self._vis.get_object_detector(self._camera.identifier)

    def check_intervals(self, shared_frame: SharedFrame):
        """Check all registered frame intervals."""
        self._current_frame_scanners = {}

        for scanner, frame_scanner in self._frame_scanners.items():
            if frame_scanner.check_scan_interval(shared_frame):
                self._current_frame_scanners[scanner] = frame_scanner

    def filter_zones(self, shared_frame: SharedFrame, objects: List[DetectedObject]):
        """Filter all zones."""
        for zone in self._zones:
            zone.filter_zone(shared_frame, objects)

    def scanner_results(self, shared_frame: SharedFrame):
        """Wait for scanner to return results."""
        for scanner, frame_scanner in self._current_frame_scanners.items():
            scanner_result = frame_scanner.result_queue.get()
            if scanner == OBJECT_DETECTOR:
                self.filter_zones(shared_frame, scanner_result)

    def process_frame(self, shared_frame: SharedFrame):
        """Process frame."""
        shared_frame.nvr_config = self._config

        self.check_intervals(shared_frame)
        self.scanner_results(shared_frame)

        self._shared_frames.remove(shared_frame)

    def run(self):
        """Read frames from camera."""
        self._logger.debug("Waiting for first frame")
        frame = self._frame_queue.get()
        self._logger.debug("First frame received")
        self.process_frame(frame)

        while not self._kill_received:
            try:
                frame = self._frame_queue.get(timeout=1)
            except Empty:
                continue
            self.process_frame(frame)

        self._logger.debug("NVR thread stopped")

    def stop(self):
        """Stop processing of events."""
        self._logger.info("Stopping NVR thread")
        self._kill_received = True

        # Stop frame grabber
        self._camera.stop_camera()

        # Stop potential recording
        if self._camera.is_recording:
            self._camera.stop_recording()
