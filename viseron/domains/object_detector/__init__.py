"""Object detector domain."""
from __future__ import annotations

import logging
import multiprocessing as mp
import time
from abc import ABC, abstractmethod
from queue import Empty, Queue
from typing import Any, Dict

import voluptuous as vol
from setproctitle import setproctitle

from viseron.components.data_stream import COMPONENT as DATA_STREAM_COMPONENT
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import SharedFrame, SharedFrames
from viseron.helpers import pop_if_full
from viseron.helpers.mprt_monkeypatch import (  # type: ignore
    remove_shm_from_resource_tracker,
)
from viseron.helpers.schemas import COORDINATES_SCHEMA, MIN_MAX_SCHEMA
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    CONFIG_COORDINATES,
    CONFIG_FPS,
    CONFIG_LABEL_CONFIDENCE,
    CONFIG_LABEL_HEIGHT_MAX,
    CONFIG_LABEL_HEIGHT_MIN,
    CONFIG_LABEL_LABEL,
    CONFIG_LABEL_POST_PROCESSOR,
    CONFIG_LABEL_REQUIRE_MOTION,
    CONFIG_LABEL_TRIGGER_RECORDER,
    CONFIG_LABEL_WIDTH_MAX,
    CONFIG_LABEL_WIDTH_MIN,
    CONFIG_LABELS,
    CONFIG_LOG_ALL_OBJECTS,
    CONFIG_MASK,
    CONFIG_MAX_FRAME_AGE,
    DATA_OBJECT_DETECTOR_RESULT,
    DEFAULT_FPS,
    DEFAULT_LABEL_CONFIDENCE,
    DEFAULT_LABEL_HEIGHT_MAX,
    DEFAULT_LABEL_HEIGHT_MIN,
    DEFAULT_LABEL_POST_PROCESSOR,
    DEFAULT_LABEL_REQUIRE_MOTION,
    DEFAULT_LABEL_TRIGGER_RECORDER,
    DEFAULT_LABEL_WIDTH_MAX,
    DEFAULT_LABEL_WIDTH_MIN,
    DEFAULT_LABELS,
    DEFAULT_LOG_ALL_OBJECTS,
    DEFAULT_MASK,
    DEFAULT_MAX_FRAME_AGE,
)

DOMAIN = "object_detector"


def ensure_min_max(label: dict) -> dict:
    """Ensure min values are not larger than max values."""
    if label["height_min"] >= label["height_max"]:
        raise vol.Invalid("height_min may not be larger or equal to height_max")
    if label["width_min"] >= label["width_max"]:
        raise vol.Invalid("width_min may not be larger or equal to width_max")
    return label


LABEL_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_LABEL_LABEL): str,
        vol.Optional(
            CONFIG_LABEL_CONFIDENCE, default=DEFAULT_LABEL_CONFIDENCE
        ): MIN_MAX_SCHEMA,
        vol.Optional(
            CONFIG_LABEL_HEIGHT_MIN, default=DEFAULT_LABEL_HEIGHT_MIN
        ): MIN_MAX_SCHEMA,
        vol.Optional(
            CONFIG_LABEL_HEIGHT_MAX, default=DEFAULT_LABEL_HEIGHT_MAX
        ): MIN_MAX_SCHEMA,
        vol.Optional(
            CONFIG_LABEL_WIDTH_MIN, default=DEFAULT_LABEL_WIDTH_MIN
        ): MIN_MAX_SCHEMA,
        vol.Optional(
            CONFIG_LABEL_WIDTH_MAX, default=DEFAULT_LABEL_WIDTH_MAX
        ): MIN_MAX_SCHEMA,
        vol.Optional(
            CONFIG_LABEL_TRIGGER_RECORDER, default=DEFAULT_LABEL_TRIGGER_RECORDER
        ): bool,
        vol.Optional(
            CONFIG_LABEL_REQUIRE_MOTION, default=DEFAULT_LABEL_REQUIRE_MOTION
        ): bool,
        vol.Optional(
            CONFIG_LABEL_POST_PROCESSOR, default=DEFAULT_LABEL_POST_PROCESSOR
        ): vol.Any(str, None),
    },
    ensure_min_max,
)

CAMERA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_FPS, default=DEFAULT_FPS): vol.All(
            vol.Any(float, int), vol.Coerce(float), vol.Range(min=0.0)
        ),
        vol.Optional(CONFIG_LABELS, default=DEFAULT_LABELS): vol.Any(
            [], [LABEL_SCHEMA]
        ),
        vol.Optional(CONFIG_MAX_FRAME_AGE, default=DEFAULT_MAX_FRAME_AGE): vol.All(
            vol.Any(float, int), vol.Coerce(float), vol.Range(min=0.0)
        ),
        vol.Optional(CONFIG_LOG_ALL_OBJECTS, default=DEFAULT_LOG_ALL_OBJECTS): bool,
        vol.Optional(CONFIG_MASK, default=DEFAULT_MASK): [
            {vol.Required(CONFIG_COORDINATES): COORDINATES_SCHEMA}
        ],
    }
)

LOGGER = logging.getLogger(__name__)


class AbstractObjectDetector(ABC):
    """Abstract Object Detector."""

    def __init__(self, vis, config):
        self._vis = vis
        self._config = config

        self._shared_frames = SharedFrames()

        self.input_queue: Any = Queue(maxsize=100)
        input_thread = RestartableThread(
            target=self._process_input_queue,
            name=f"object_detector.{self.name}",
            register=True,
            daemon=True,
        )
        input_thread.start()

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

        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)

    def _process_input_queue(self):
        """Read from thread queue and put to multiprocessing queue."""
        while True:
            shared_frame: SharedFrame = self.input_queue.get()
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

            if (frame_age := time.time() - shared_frame.capture_time) > self._config[
                "cameras"
            ][shared_frame.camera_identifier][CONFIG_FPS]:
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

    @property
    @abstractmethod
    def fps(self) -> str:
        """Return object detector fps."""

    def stop(self):
        """Stop detection process."""
        LOGGER.debug("Sending exit event to object detector")
        self._process_frames_proc_exit.set()
        self._process_frames_proc.join()
        LOGGER.debug("Object detector exited")
