"""Object detector domain."""
from __future__ import annotations

import logging
import multiprocessing as mp
import time
from abc import ABC, abstractmethod
from queue import Empty, Queue
from typing import Any, Dict

from setproctitle import setproctitle

from viseron.components.data_stream import COMPONENT as DATA_STREAM_COMPONENT
from viseron.components.nvr.const import CONFIG_MAX_FRAME_AGE, CONFIG_OBJECT_DETECTOR
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import SharedFrame, SharedFrames
from viseron.helpers import calculate_relative_coords, pop_if_full
from viseron.helpers.mprt_monkeypatch import (  # type: ignore
    remove_shm_from_resource_tracker,
)
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import DATA_OBJECT_DETECTOR_RESULT

LOGGER = logging.getLogger(__name__)


class AbstractObjectDetector(ABC):
    """Abstract Object Detector."""

    def __init__(self, vis, config):
        self._vis = vis
        self._config = config

        self._shared_frames = SharedFrames()

        self._output_queue: Any = mp.Queue(maxsize=100)
        output_thread = RestartableThread(
            target=self._process_output_queue,
            name=f"object_detector.{self.name}",
            register=True,
            daemon=True,
        )
        output_thread.start()

        self._process_frames_proc_exit = mp.Event()
        self._process_queue: Any = mp.Queue(maxsize=100)
        self._process_frames_proc = mp.Process(
            target=self._process_frames,
            name=f"object_detector.{self.name}",
            args=(
                self._process_frames_proc_exit,
                self._process_queue,
                self._output_queue,
            ),
        )
        self._process_frames_proc.start()

        self._input_queue: Any = Queue(maxsize=100)
        input_thread = RestartableThread(
            target=self._process_input_queue,
            name=f"object_detector.{self.name}",
            register=True,
            daemon=True,
        )
        input_thread.start()

        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)

    def _process_input_queue(self):
        """Read from thread queue and put to multiprocessing queue."""
        while True:
            shared_frame: SharedFrame = self._input_queue.get()
            self._process_queue.put(shared_frame)

    def _process_output_queue(self):
        """Read from multiprocessing queue and put to thread queue."""
        while True:
            output_data = self._output_queue.get()
            shared_frame: SharedFrame = output_data["shared_frame"]
            objects = output_data["objects"]
            self._vis.data[DATA_STREAM_COMPONENT].publish_data(
                DATA_OBJECT_DETECTOR_RESULT.format(
                    camera_identifier=shared_frame.camera_identifier
                ),
                objects,
            )

    # @abstractmethod
    def preprocess(self, frame):
        """Perform preprocessing of frame before running detection."""
        return frame

    def _process_frames(self, exit_event, process_queue, output_queue):
        """Process frame and send it to the detector."""
        remove_shm_from_resource_tracker()
        setproctitle(f"viseron_object_detector_{self.name}")
        detector_queue: Dict[str, Any] = Queue(maxsize=100)
        detector_thread = RestartableThread(
            target=self.object_detection,
            name=f"object_detector.{self.name}",
            args=(detector_queue, output_queue),
            register=True,
            daemon=True,
        )
        detector_thread.start()

        while not exit_event.is_set():
            try:
                shared_frame: SharedFrame = process_queue.get(timeout=1)
            except Empty:
                continue

            decoded_frame = self._shared_frames.get_decoded_frame_rgb(shared_frame)
            preprocessed_frame = self.preprocess(decoded_frame)
            pop_if_full(
                detector_queue,
                {
                    "shared_frame": shared_frame,
                    "preprocessed_frame": preprocessed_frame,
                },
                logger=LOGGER,
            )
            self._shared_frames.close(shared_frame)
        LOGGER.debug("Exiting object detector process")

    def object_detection(self, detector_queue, output_queue):
        """Perform object detection and publish the results."""
        while True:
            input_data = detector_queue.get()
            shared_frame: SharedFrame = input_data["shared_frame"]
            preprocessed_frame = input_data["preprocessed_frame"]

            if (
                frame_age := time.time() - shared_frame.capture_time
            ) > shared_frame.nvr_config[CONFIG_OBJECT_DETECTOR][CONFIG_MAX_FRAME_AGE]:
                LOGGER.debug(f"Frame is {frame_age} seconds old. Discarding")
                continue

            objects = self.return_objects(preprocessed_frame)
            pop_if_full(
                output_queue,
                {
                    "shared_frame": shared_frame,
                    "objects": objects,
                },
            )
            self._shared_frames.close(shared_frame)

    @abstractmethod
    def return_objects(self, frame):
        """Perform object detection."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return object detector name."""

    def stop(self):
        """Stop detection process."""
        LOGGER.debug("Sending exit event to object detector")
        self._process_frames_proc_exit.set()
        self._process_frames_proc.join()
        LOGGER.debug("Object detector exited")


class DetectedObject:
    """Object that holds a detected object.

    All coordinates and metrics are relative to make it easier to do calculations on
    different image resolutions.
    """

    def __init__(
        self, label, confidence, x1, y1, x2, y2, relative=True, image_res=None
    ):
        self._label = label
        self._confidence = round(float(confidence), 3)
        if relative:
            self._rel_x1 = float(round(x1, 3))
            self._rel_y1 = float(round(y1, 3))
            self._rel_x2 = float(round(x2, 3))
            self._rel_y2 = float(round(y2, 3))
        else:
            (
                self._rel_x1,
                self._rel_y1,
                self._rel_x2,
                self._rel_y2,
            ) = calculate_relative_coords((x1, y1, x2, y2), image_res)

        self._rel_width = float(round(self._rel_x2 - self._rel_x1, 3))
        self._rel_height = float(round(self._rel_y2 - self._rel_y1, 3))
        self._trigger_recorder = False
        self._relevant = False
        self._filter_hit = None

    @property
    def label(self):
        """Return label of the object."""
        return self._label

    @property
    def confidence(self):
        """Return confidence of the object."""
        return self._confidence

    @property
    def rel_width(self):
        """Return relative width of the object."""
        return self._rel_width

    @property
    def rel_height(self):
        """Return relative height of the object."""
        return self._rel_height

    @property
    def rel_x1(self):
        """Return relative x1 of the object."""
        return self._rel_x1

    @property
    def rel_y1(self):
        """Return relative y1 of the object."""
        return self._rel_y1

    @property
    def rel_x2(self):
        """Return relative x2 of the object."""
        return self._rel_x2

    @property
    def rel_y2(self):
        """Return relative y2 of the object."""
        return self._rel_y2

    @property
    def formatted(self):
        """Return object data in a single dictionary."""
        payload = {}
        payload["label"] = self.label
        payload["confidence"] = self.confidence
        payload["rel_width"] = self.rel_width
        payload["rel_height"] = self.rel_height
        payload["rel_x1"] = self.rel_x1
        payload["rel_y1"] = self.rel_y1
        payload["rel_x2"] = self.rel_x2
        payload["rel_y2"] = self.rel_y2
        return payload

    @property
    def trigger_recorder(self):
        """Return if object should trigger the recorder."""
        return self._trigger_recorder

    @trigger_recorder.setter
    def trigger_recorder(self, value):
        self._trigger_recorder = value

    @property
    def relevant(self):
        """Return if object is relevant.

        Relevant means it passed through all filters.
        This does not mean the object will trigger the recorder.
        """
        return self._relevant

    @relevant.setter
    def relevant(self, value):
        self._relevant = value

    @property
    def filter_hit(self):
        """Return which filter that discarded the object."""
        return self._filter_hit

    @filter_hit.setter
    def filter_hit(self, value):
        self._filter_hit = value
