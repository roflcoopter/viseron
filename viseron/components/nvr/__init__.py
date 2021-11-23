"""NVR component."""

import logging
import threading
import traceback
from queue import Empty, Queue
from typing import Dict

import voluptuous as vol

from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.shared_frames import SharedFrame, SharedFrames
from viseron.domains.motion_detector.const import (
    DATA_MOTION_DETECTOR_RESULT,
    DATA_MOTION_DETECTOR_SCAN,
)
from viseron.domains.object_detector.const import (
    DATA_OBJECT_DETECTOR_RESULT,
    DATA_OBJECT_DETECTOR_SCAN,
)
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.helpers.filter import Filter
from viseron.helpers.validators import ensure_slug
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import COMPONENT

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


NVR_SCHEMA = vol.Schema({})


OBJECT_DETECTOR = "object_detector"
MOTION_DETECTOR = "motion_detector"


def validate_nvr_config(config, camera_identifier):
    """Validate the config of an NVR entry."""
    try:
        return NVR_SCHEMA(config)
    except vol.Invalid as ex:
        LOGGER.exception(f"Error setting up nvr for camera {camera_identifier}: {ex}")
        return False
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Unknown error calling %s CONFIG_SCHEMA", camera_identifier)
        return False
    return True


def setup(vis, config):
    """Set up the nvr component."""
    config = config[COMPONENT]
    for camera_identifier in config.keys():
        if config[camera_identifier] is None:
            config[camera_identifier] = {}

        validated_config = validate_nvr_config(
            config[camera_identifier], camera_identifier
        )
        if validated_config or validated_config == {}:
            try:
                nvr = NVR(vis, validated_config, camera_identifier)
                vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, nvr.stop)
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.error(
                    f"Uncaught exception setting up nvr for camera {camera_identifier}:"
                    f" {ex}\n"
                    f"{traceback.print_exc()}"
                )

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
        self._scan_fps = scan_fps
        self._scan_interval = None

        self.scan = threading.Event()
        self._frame_number = 0
        self.result_queue = Queue(maxsize=10)

        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self._data_stream.subscribe_data(topic_result, self.result_queue)

        self.calculate_scan_interval(output_fps)

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

    def calculate_scan_interval(self, output_fps):
        """Calculate the frame scan interval."""
        self._scan_interval = round(output_fps / self.scan_fps)

    @property
    def scan_fps(self):
        """Return scan fps of scanner."""
        return self._scan_fps

    @property
    def scan_interval(self):
        """Return scan interval of scanner."""
        return self._scan_interval


class NVR:
    """NVR class that orchestrates all handling of camera streams."""

    def __init__(self, vis, config: dict, camera_identifier: str):
        vis.data.setdefault(COMPONENT, {})[camera_identifier] = self
        self._vis = vis
        self._config = config
        self._camera: AbstractCamera = vis.get_registered_camera(camera_identifier)

        self.setup_loggers()
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.debug(f"Initializing NVR for camera {self._camera.name}")

        self._start_recorder = False
        self._idle_frames = 0
        self._kill_received = False
        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self._shared_frames = SharedFrames()

        self._frame_scanners = {}
        self._current_frame_scanners: Dict[str, FrameIntervalCalculator] = {}

        self._motion_only_frames = 0
        self._motion_recorder_keepalive_reached = False
        _motion_detector = self.get_motion_detector()
        self._motion_detector = _motion_detector
        if self._motion_detector:
            self._frame_scanners[MOTION_DETECTOR] = FrameIntervalCalculator(
                vis,
                MOTION_DETECTOR,
                self._logger,
                self._camera.output_fps,
                self._motion_detector.fps,
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
            and self._object_detector
            and self._object_detector.scan_on_motion_only
        ):
            self._frame_scanners[MOTION_DETECTOR].scan.set()
            if self._object_detector:
                self._frame_scanners[OBJECT_DETECTOR].scan.clear()
        else:
            if self._object_detector:
                self._frame_scanners[OBJECT_DETECTOR].scan.set()
            if self._motion_detector:
                self._frame_scanners[MOTION_DETECTOR].scan.clear()

        self._frame_queue: "Queue[bytes]" = Queue(maxsize=100)
        self._data_stream.subscribe_data(
            self._camera.frame_bytes_topic, self._frame_queue
        )
        self._nvr_thread = RestartableThread(
            name=str(self),
            target=self.run,
            stop_target=self.stop,
            daemon=False,
            register=True,
        )
        self._nvr_thread.start()

        if self._frame_scanners:
            self.calculate_output_fps()

        self._camera.start_camera()
        self._logger.debug(f"NVR for camera {self._camera.name} initialized")

    def setup_loggers(self):
        """Set up custom log names and levels."""
        self._logger = logging.getLogger(__name__ + "." + self._camera.identifier)
        self._motion_logger = logging.getLogger(
            __name__ + "." + self._camera.identifier + ".motion"
        )

    def get_object_detector(self):
        """Get object detector."""
        return self._vis.get_object_detector(self._camera.identifier)

    def get_motion_detector(self):
        """Get motion detector."""
        return self._vis.get_motion_detector(self._camera.identifier)

    def calculate_output_fps(self):
        """Calculate the camera output fps based on registered frame scanners."""
        highest_fps = max(
            [scanner.scan_fps for scanner in self._frame_scanners.values()]
        )
        self._camera.output_fps = highest_fps
        for scanner in self._frame_scanners.values():
            scanner.calculate_scan_interval(self._camera.output_fps)

    def check_intervals(self, shared_frame: SharedFrame):
        """Check all registered frame intervals."""
        self._current_frame_scanners = {}

        for scanner, frame_scanner in self._frame_scanners.items():
            if frame_scanner.check_scan_interval(shared_frame):
                self._current_frame_scanners[scanner] = frame_scanner

    def scanner_results(self):
        """Wait for scanner to return results."""
        for frame_scanner in self._current_frame_scanners.values():
            while True:
                try:  # Make sure we dont wait forever if stop is requested
                    frame_scanner.result_queue.get(timeout=1)
                    break
                except Empty:
                    if self._kill_received:
                        return
                    continue

    def event_over_check_motion(
        self, obj: DetectedObject, object_filters: Dict[str, Filter]
    ):
        """Check if motion should stop the recorder."""
        if object_filters.get(obj.label) and object_filters[obj.label].require_motion:
            if self._motion_detector.motion_detected:
                self._motion_recorder_keepalive_reached = False
                self._motion_only_frames = 0
                return False
        else:
            self._motion_recorder_keepalive_reached = False
            self._motion_only_frames = 0
            return False
        return True

    def event_over_check_object(
        self, obj: DetectedObject, object_filters: Dict[str, Filter]
    ):
        """Check if object should stop the recorder."""
        if obj.trigger_recorder:
            if self._motion_detector:
                if not self.event_over_check_motion(obj, object_filters):
                    return False
            else:
                return False
        return True

    def event_over(self):
        """Return if ongoing motion and/or object detection is over."""
        if self._object_detector:
            for obj in self._object_detector.objects_in_fov:
                if not self.event_over_check_object(
                    obj, self._object_detector.object_filters
                ):
                    return False

            for zone in self._object_detector.zones:
                for obj in zone.objects_in_zone:
                    if not self.event_over_check_object(obj, zone.object_filters):
                        return False

        if (
            self._motion_detector
            and self._motion_detector.recorder_keepalive
            and self._motion_detector.motion_detected
        ):
            # Only allow motion to keep event active for a specified period of time
            if self._motion_only_frames >= (
                self._camera.output_fps * self._motion_detector.max_recorder_keepalive
            ):
                if not self._motion_recorder_keepalive_reached:
                    self._motion_recorder_keepalive_reached = True
                    self._logger.debug(
                        "Motion has kept recorder alive for longer than "
                        "max_recorder_keepalive, event considered over anyway"
                    )
                return True
            self._motion_only_frames += 1
            return False
        return True

    def trigger_recorder(self, obj: DetectedObject, object_filters: Dict[str, Filter]):
        """Check if object should start the recorder."""
        # Discard object if it requires motion but motion is not detected
        if (
            obj.trigger_recorder
            and object_filters.get(obj.label)
            and object_filters.get(obj.label).require_motion  # type: ignore
            and self._motion_detector
            and not self._motion_detector.motion_detected
        ):
            return False

        if obj.trigger_recorder:
            return True

        return False

    def process_object_event(self):
        """Process any detected objects to see if recorder should start."""
        for obj in self._object_detector.objects_in_fov:
            if self.trigger_recorder(obj, self._object_detector.object_filters):
                self._start_recorder = True
                return

        for zone in self._object_detector.zones:
            for obj in zone.objects_in_zone:
                if self.trigger_recorder(obj, zone.object_filters):
                    self._start_recorder = True
                    return

    def process_motion_event(self):
        """Process motion to see if it has started or stopped."""
        if self._motion_detector and self._motion_detector.motion_detected:
            if (
                self._object_detector
                and self._object_detector.scan_on_motion_only
                and not self._frame_scanners[OBJECT_DETECTOR].scan.is_set()
            ):
                self._frame_scanners[OBJECT_DETECTOR].scan.set()
                self._logger.debug("Starting object detector")

            if self._motion_detector.trigger_recorder and not self._camera.is_recording:
                self._start_recorder = True

        elif (
            self._object_detector
            and self._frame_scanners[OBJECT_DETECTOR].scan.is_set()
            and not self._camera.is_recording
            and self._object_detector.scan_on_motion_only
        ):
            self._logger.debug("Not recording, pausing object detector")
            self._frame_scanners[OBJECT_DETECTOR].scan.clear()

    def start_recorder(self, shared_frame):
        """Start recorder."""
        self._camera.start_recorder(shared_frame, self._object_detector.objects_in_fov)

        if (
            self._motion_detector
            and self._motion_detector.recorder_keepalive
            and not self._frame_scanners[MOTION_DETECTOR].scan.is_set()
        ):
            self._frame_scanners[MOTION_DETECTOR].scan.set()
            self._logger.info("Starting motion detector")

    def stop_recorder(self):
        """Stop recorder."""
        if self._idle_frames % self._camera.output_fps == 0:
            self._logger.info(
                "Stopping recording in: {}".format(
                    int(
                        self._camera.recorder.idle_timeout
                        - (self._idle_frames / self._camera.output_fps)
                    )
                )
            )

        if self._idle_frames >= (
            self._camera.output_fps * self._camera.recorder.idle_timeout
        ):
            if (
                self._motion_detector
                and self._object_detector
                and not self._object_detector.scan_on_motion_only
                and not self._motion_detector.trigger_recorder
            ):
                self._frame_scanners[MOTION_DETECTOR].scan.clear()
                self._logger.info("Pausing motion detector")

            self._camera.stop_recorder()

    def process_frame(self, shared_frame: SharedFrame):
        """Process frame."""
        shared_frame.nvr_config = self._config

        self.check_intervals(shared_frame)
        self.scanner_results()
        if not self._camera.is_recording and self._object_detector:
            self.process_object_event()
        if not self._camera.is_recording and self._motion_detector:
            self.process_motion_event()

    def process_recorder(self, shared_frame: SharedFrame):
        """Check if we should start or stop the recorder."""
        if self._start_recorder:
            self._start_recorder = False
            self.start_recorder(shared_frame)
        elif self._camera.is_recording and self.event_over():
            self._idle_frames += 1
            self.stop_recorder()
        else:
            self._idle_frames = 0

    def run(self):
        """Read frames from camera."""
        self._logger.debug("Waiting for first frame")
        shared_frame = self._frame_queue.get()
        self._logger.debug("First frame received")
        self.process_frame(shared_frame)

        while not self._kill_received:
            try:
                shared_frame = self._frame_queue.get(timeout=1)
            except Empty:
                continue
            self.process_frame(shared_frame)
            self.process_recorder(shared_frame)

            self._shared_frames.remove(shared_frame)
        self._logger.debug("NVR thread stopped")

    def stop(self):
        """Stop processing of events."""
        self._logger.info("Stopping NVR thread")
        # Stop frame grabber
        self._camera.stop_camera()

        self._kill_received = True
        self._nvr_thread.join()

        # Stop potential recording
        if self._camera.is_recording:
            self._camera.stop_recorder()

        # Empty frame queue before exiting
        while True:
            try:
                shared_frame = self._frame_queue.get(timeout=1)
            except Empty:
                break
            self._shared_frames.remove(shared_frame)
