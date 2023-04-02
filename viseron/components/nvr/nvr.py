"""nvr domain.

This domain is NOT meant to be subclassed or implemented by other components.
The reason for using a domain instead of a component is to use the domain dependencies
built into domain setup.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from queue import Empty, Queue
from typing import TYPE_CHECKING, Literal

import numpy as np

from viseron.components.data_stream import COMPONENT as DATA_STREAM_COMPONENT
from viseron.components.nvr.const import COMPONENT
from viseron.const import DOMAIN_IDENTIFIERS, VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.domains.motion_detector.const import (
    DATA_MOTION_DETECTOR_RESULT,
    DATA_MOTION_DETECTOR_SCAN,
)
from viseron.domains.object_detector.const import (
    DATA_OBJECT_DETECTOR_RESULT,
    DATA_OBJECT_DETECTOR_SCAN,
)
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.exceptions import DomainNotRegisteredError
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    DATA_PROCESSED_FRAME_TOPIC,
    EVENT_OPERATION_STATE,
    EVENT_SCAN_FRAMES,
    MOTION_DETECTOR,
    OBJECT_DETECTOR,
)
from .sensor import OperationStateSensor

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.data_stream import DataStream
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.camera.shared_frames import SharedFrame
    from viseron.domains.motion_detector import AbstractMotionDetectorScanner, Contours
    from viseron.domains.object_detector import AbstractObjectDetector
    from viseron.helpers.filter import Filter

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the edgetpu object_detector domain."""
    object_detector: AbstractObjectDetector | Literal[False] = False
    if (
        OBJECT_DETECTOR in vis.data[DOMAIN_IDENTIFIERS]
        and identifier in vis.data[DOMAIN_IDENTIFIERS][OBJECT_DETECTOR]
    ):
        try:
            object_detector = vis.get_registered_domain(OBJECT_DETECTOR, identifier)
        except DomainNotRegisteredError:
            object_detector = False

    motion_detector: AbstractMotionDetectorScanner | Literal[False] = False
    if (
        MOTION_DETECTOR in vis.data[DOMAIN_IDENTIFIERS]
        and identifier in vis.data[DOMAIN_IDENTIFIERS][MOTION_DETECTOR]
    ):
        try:
            motion_detector = vis.get_registered_domain(MOTION_DETECTOR, identifier)
        except DomainNotRegisteredError:
            motion_detector = False

    if object_detector is False and motion_detector is False:
        LOGGER.error(
            f"Failed setup of domain nvr for camera {identifier}. "
            "At least one object or motion detector has to be configured"
        )
        return False

    NVR(vis, config, identifier, object_detector, motion_detector)

    return True


@dataclass
class DataProcessedFrame:
    """Processed frame that is sent on DATA_PROCESSED_FRAME_TOPIC."""

    frame: np.ndarray
    objects_in_fov: list[DetectedObject] | None
    motion_contours: Contours | None


@dataclass
class EventOperationState:
    """Hold information of current state of operation."""

    camera_identifier: str
    operation_state: str


@dataclass
class EventScanFrames:
    """Event dispatched on starting/stopping scan of frames."""

    camera_identifier: str
    scan: bool


class FrameIntervalCalculator:
    """Mark frames for scanning.

    This class is used to mark frames for scanning. The class will calculate the
    interval between frames that should be scanned. The interval is calculated based
    on the output FPS and the scan FPS.

    Note: This class should be refactored and moved into the Camera domain.
    """

    def __init__(
        self,
        vis: Viseron,
        camera_identifier,
        name,
        logger,
        output_fps,
        scan_fps,
        topic_scan,
        topic_result,
    ) -> None:
        self._vis = vis
        self._camera_identifier = camera_identifier
        self._name = name
        self._topic_scan = topic_scan
        if scan_fps > output_fps:
            logger.warning(
                f"FPS for {name} is too high, highest possible FPS is {output_fps}"
            )
            scan_fps = output_fps
        self._scan: bool = False
        self._scan_fps = scan_fps
        self._scan_interval = 0
        self._scan_error: bool = False

        self._frame_number = 0
        self.result_queue: Queue = Queue(maxsize=1)

        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self._data_stream.subscribe_data(topic_result, self.result_queue)

        self.calculate_scan_interval(output_fps)

    def check_scan_interval(self, shared_frame: SharedFrame) -> bool:
        """Check if frame should be marked for scanning."""
        if self.scan:
            if self._frame_number % self._scan_interval == 0:
                self._frame_number = 1
                self._data_stream.publish_data(self._topic_scan, shared_frame)
                return True
            self._frame_number += 1
        else:
            self._frame_number = 0
        return False

    def calculate_scan_interval(self, output_fps) -> None:
        """Calculate the frame scan interval."""
        self._scan_interval = round(output_fps / self.scan_fps)

    @property
    def scan(self):
        """Return if frames should be scanned."""
        return self._scan

    @scan.setter
    def scan(self, value: bool) -> None:
        self._scan = value
        self._vis.dispatch_event(
            EVENT_SCAN_FRAMES.format(
                camera_identifier=self._camera_identifier, scanner_name=self._name
            ),
            EventScanFrames(camera_identifier=self._camera_identifier, scan=value),
        )

    @property
    def scan_fps(self):
        """Return scan fps of scanner."""
        return self._scan_fps

    @property
    def scan_interval(self):
        """Return scan interval of scanner."""
        return self._scan_interval

    @property
    def scan_error(self):
        """Return if the last scan failed."""
        return self._scan_error

    @scan_error.setter
    def scan_error(self, value: bool) -> None:
        self._scan_error = value


class NVR:
    """NVR class that orchestrates all handling of camera streams."""

    def __init__(
        self,
        vis: Viseron,
        config: dict,
        camera_identifier: str,
        object_detector: AbstractObjectDetector | Literal[False],
        motion_detector: AbstractMotionDetectorScanner | Literal[False],
    ) -> None:
        self._vis = vis
        self._config = config
        self._camera: AbstractCamera = vis.get_registered_domain(
            CAMERA_DOMAIN, camera_identifier
        )

        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.debug(f"Initializing NVR for camera {self._camera.name}")

        self._start_recorder = False
        self._idle_frames = 0
        self._kill_received = False
        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self._removal_timers: list[threading.Timer] = []
        self._operation_state = None

        self._frame_scanners: dict[str, FrameIntervalCalculator] = {}
        self._current_frame_scanners: dict[str, FrameIntervalCalculator] = {}
        self._frame_scanner_errors: list[str] = []
        self._topic_processed_frame = DATA_PROCESSED_FRAME_TOPIC.format(
            camera_identifier=camera_identifier
        )

        self._motion_only_frames = 0
        self._motion_recorder_keepalive_reached = False
        self._motion_detector = motion_detector
        if self._motion_detector:
            self._frame_scanners[MOTION_DETECTOR] = FrameIntervalCalculator(
                vis,
                self._camera.identifier,
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

        self._object_detector = object_detector
        if self._object_detector:
            self._frame_scanners[OBJECT_DETECTOR] = FrameIntervalCalculator(
                vis,
                self._camera.identifier,
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
            self._frame_scanners[MOTION_DETECTOR].scan = True
            if self._object_detector:
                self._frame_scanners[OBJECT_DETECTOR].scan = False
        else:
            if self._object_detector and self._motion_detector:
                self._frame_scanners[OBJECT_DETECTOR].scan = True
                self._frame_scanners[MOTION_DETECTOR].scan = False
            if self._object_detector:
                self._frame_scanners[OBJECT_DETECTOR].scan = True
            elif self._motion_detector:
                self._frame_scanners[MOTION_DETECTOR].scan = True

        self._frame_queue: Queue[bytes] = Queue(maxsize=100)
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
            self.calculate_output_fps(list(self._frame_scanners.values()))

        vis.data.setdefault(COMPONENT, {})[camera_identifier] = self
        vis.add_entity(COMPONENT, OperationStateSensor(vis, self))

        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)

        self._camera.start_camera()
        self._logger.info(f"NVR for camera {self._camera.name} initialized")

    def calculate_output_fps(self, scanners: list[FrameIntervalCalculator]) -> None:
        """Calculate output fps based on fps of all scanners."""
        self._camera.calculate_output_fps(scanners)
        for scanner in scanners:
            scanner.calculate_scan_interval(self._camera.output_fps)

    @property
    def operation_state(self):
        """Return state of operation."""
        return self._operation_state

    @operation_state.setter
    def operation_state(self, value) -> None:
        """Set state of operation."""
        if value == self._operation_state:
            return

        self._operation_state = value
        self._vis.dispatch_event(
            EVENT_OPERATION_STATE.format(camera_identifier=self._camera.identifier),
            EventOperationState(
                camera_identifier=self._camera.identifier,
                operation_state=value,
            ),
        )

    def update_operation_state(self) -> None:
        """Update operation state."""
        operation_state = "idle"
        if self._frame_scanner_errors:
            operation_state = "error_scanning_frame"
        elif self._camera.is_recording:
            operation_state = "recording"
        elif not self._camera.is_on:
            operation_state = "idle"
        elif self._object_detector and self._frame_scanners[OBJECT_DETECTOR].scan:
            operation_state = "scanning_for_objects"
        elif self._motion_detector and self._frame_scanners[MOTION_DETECTOR].scan:
            operation_state = "scanning_for_motion"

        self.operation_state = operation_state

    def check_intervals(self, shared_frame: SharedFrame) -> None:
        """Check all registered frame intervals."""
        self._current_frame_scanners = {}

        for scanner, frame_scanner in self._frame_scanners.items():
            if frame_scanner.check_scan_interval(shared_frame):
                self._current_frame_scanners[scanner] = frame_scanner

    def scanner_results(self) -> None:
        """Wait for scanner to return results."""
        self._frame_scanner_errors = []
        for name, frame_scanner in self._current_frame_scanners.items():
            frame_scanner.scan_error = False
            try:
                # Wait for scanner to return.
                # We dont care about the result since its referenced directly
                # from the scanner instead of storing it locally
                frame_scanner.result_queue.get(
                    timeout=3,
                )
            except Empty:  # Make sure we dont wait forever
                if self._kill_received:
                    return
                self._logger.error(f"Failed to retrieve result for {name}")
                frame_scanner.scan_error = True
                self._frame_scanner_errors.append(name)

    def event_over_check_motion(
        self, obj: DetectedObject, object_filters: dict[str, Filter]
    ) -> bool:
        """Check if motion should stop the recorder."""
        if object_filters.get(obj.label) and object_filters[obj.label].require_motion:
            if self._motion_detector and self._motion_detector.motion_detected:
                self._motion_recorder_keepalive_reached = False
                self._motion_only_frames = 0
                return False
        else:
            self._motion_recorder_keepalive_reached = False
            self._motion_only_frames = 0
            return False
        return True

    def event_over_check_object(
        self, obj: DetectedObject, object_filters: dict[str, Filter]
    ) -> bool:
        """Check if object should stop the recorder."""
        if obj.trigger_recorder:
            if self._motion_detector:
                if not self.event_over_check_motion(obj, object_filters):
                    return False
            else:
                return False
        return True

    def event_over(self) -> bool:
        """Return if ongoing motion and/or object detection is over."""
        if (
            self._object_detector
            and self._frame_scanners[OBJECT_DETECTOR].scan
            and not self._frame_scanners[OBJECT_DETECTOR].scan_error
        ):
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
            and self._frame_scanners[MOTION_DETECTOR].scan
            and not self._frame_scanners[MOTION_DETECTOR].scan_error
            and self._motion_detector.recorder_keepalive
            and self._motion_detector.motion_detected
        ):
            # Only allow motion to keep event active for a specified period of time
            if (
                self._motion_detector.max_recorder_keepalive
                and self._motion_only_frames
                >= (
                    self._camera.output_fps
                    * self._motion_detector.max_recorder_keepalive
                )
            ):
                if not self._motion_recorder_keepalive_reached:
                    self._motion_recorder_keepalive_reached = True
                    self._logger.debug(
                        "Motion has kept recorder alive for longer than "
                        "max_recorder_keepalive "
                        f"({self._motion_detector.max_recorder_keepalive}s), "
                        "event considered over anyway"
                    )
                return True
            self._motion_only_frames += 1
            return False
        return True

    def trigger_recorder(
        self, obj: DetectedObject, object_filters: dict[str, Filter]
    ) -> bool:
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

    def process_object_event(self) -> None:
        """Process any detected objects to see if recorder should start."""
        # Only process objects if object detection is enabled
        if not self._object_detector:
            return

        # Only process objects if we are not already recording
        if self._camera.is_recording:
            return

        # Only process objects if we are actively scanning for objects and the last
        # scan did not return an error
        if (
            self._object_detector
            and not self._frame_scanners[OBJECT_DETECTOR].scan
            and not self._frame_scanners[OBJECT_DETECTOR].scan_error
        ):
            return

        for obj in self._object_detector.objects_in_fov:
            if self.trigger_recorder(obj, self._object_detector.object_filters):
                self._start_recorder = True
                return

        for zone in self._object_detector.zones:
            for obj in zone.objects_in_zone:
                if self.trigger_recorder(obj, zone.object_filters):
                    self._start_recorder = True
                    return

    def process_motion_event(self) -> None:
        """Process motion to see if it has started or stopped."""
        # Only process motion if motion detection is enabled
        if not self._motion_detector:
            return

        # Only process motion if we are not already recording
        if self._camera.is_recording:
            return

        # Only process motion if we are actively scanning for motion and the last
        # scan did not return an error
        if (
            self._motion_detector
            and not self._frame_scanners[MOTION_DETECTOR].scan
            and not self._frame_scanners[MOTION_DETECTOR].scan_error
        ):
            return

        if self._motion_detector and self._motion_detector.motion_detected:
            if (
                self._object_detector
                and self._object_detector.scan_on_motion_only
                and not self._frame_scanners[OBJECT_DETECTOR].scan
            ):
                self._frame_scanners[OBJECT_DETECTOR].scan = True
                self._logger.debug("Starting object detector")

            if self._motion_detector.trigger_recorder and not self._camera.is_recording:
                self._start_recorder = True
                self._motion_only_frames = 0
                self._motion_recorder_keepalive_reached = False

        elif (
            self._object_detector
            and self._frame_scanners[OBJECT_DETECTOR].scan
            and not self._start_recorder
            and not self._camera.is_recording
            and self._object_detector.scan_on_motion_only
        ):
            self._logger.debug("Not recording, pausing object detector")
            self._frame_scanners[OBJECT_DETECTOR].scan = False

    def start_recorder(self, shared_frame) -> None:
        """Start recorder."""
        self._idle_frames = 0
        self._camera.start_recorder(
            shared_frame,
            self._object_detector.objects_in_fov if self._object_detector else None,
        )

        if (
            self._motion_detector
            and self._motion_detector.recorder_keepalive
            and not self._frame_scanners[MOTION_DETECTOR].scan
        ):
            self._frame_scanners[MOTION_DETECTOR].scan = True
            self._logger.info("Starting motion detector")

    def stop_recorder(self) -> None:
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
                self._frame_scanners[MOTION_DETECTOR].scan = False
                self._logger.info("Pausing motion detector")
            self._idle_frames = 0
            self._camera.stop_recorder()

    def process_frame(self, shared_frame: SharedFrame) -> None:
        """Process frame."""
        self.check_intervals(shared_frame)
        self.scanner_results()
        self.process_object_event()
        self.process_motion_event()

    def process_recorder(self, shared_frame: SharedFrame) -> None:
        """Check if we should start or stop the recorder."""
        if self._start_recorder:
            self._start_recorder = False
            self.start_recorder(shared_frame)
        elif self._camera.is_recording and self.event_over():
            self._idle_frames += 1
            self.stop_recorder()
        else:
            self._idle_frames = 0

    def remove_frame(self, shared_frame) -> None:
        """Remove frame after a delay.

        This makes sure all frames are cleaned up eventually.
        """
        timer = threading.Timer(
            2, self._camera.shared_frames.remove, args=(shared_frame,)
        )
        timer.start()

    def run(self) -> None:
        """Read frames from camera."""
        self._logger.debug("Waiting for first frame")
        first_frame_log = True

        while not self._kill_received:
            self.update_operation_state()
            try:
                shared_frame: SharedFrame = self._frame_queue.get(timeout=1)
            except Empty:
                continue

            if first_frame_log:
                self._logger.debug("First frame received")
                first_frame_log = False

            if (frame_age := time.time() - shared_frame.capture_time) > 1:
                self._logger.debug(f"Frame is {frame_age} seconds old. Discarding")
                self.remove_frame(shared_frame)
                continue

            self.process_frame(shared_frame)
            self.process_recorder(shared_frame)
            self._data_stream.publish_data(
                self._topic_processed_frame,
                DataProcessedFrame(
                    frame=self._camera.shared_frames.get_decoded_frame_rgb(
                        shared_frame
                    ).copy(),
                    objects_in_fov=self._object_detector.objects_in_fov
                    if self._object_detector
                    else None,
                    motion_contours=self._motion_detector.motion_contours
                    if self._motion_detector
                    else None,
                ),
            )
            self.remove_frame(shared_frame)
        self._logger.debug("NVR thread stopped")

    def stop(self) -> None:
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
            self._camera.shared_frames.remove(shared_frame)

        for timer in self._removal_timers:
            timer.cancel()

        self._camera.shared_frames.remove_all()

    @property
    def camera(self) -> AbstractCamera:
        """Return camera."""
        return self._camera

    @property
    def object_detector(self):
        """Return object_detector."""
        return self._object_detector

    @property
    def motion_detector(self):
        """Return motion_detector."""
        return self._motion_detector
