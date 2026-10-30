"""Hailo component."""

from __future__ import annotations

import logging
import multiprocessing as mp
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from viseron.components.hailo.utils import (
    get_hailo_arch,
    get_model,
    get_model_size,
    load_labels,
)
from viseron.domains import RequireDomain, setup_domain
from viseron.domains.object_detector import (
    BASE_CONFIG_SCHEMA as OBJECT_DETECTOR_BASE_CONFIG_SCHEMA,
)
from viseron.domains.object_detector.const import CONFIG_CAMERAS
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.exceptions import ComponentNotReady, ViseronError
from viseron.helpers import letterbox_resize, pop_if_full
from viseron.helpers.child_process_context import get_child_process_context
from viseron.helpers.child_process_worker import ChildProcessWorker
from viseron.helpers.validators import Maybe, PathExists, Url

from .const import (
    COMPONENT,
    CONFIG_LABEL_PATH,
    CONFIG_MAX_DETECTIONS,
    CONFIG_MODEL_PATH,
    CONFIG_MULTI_PROCESS_SERVICE,
    CONFIG_OBJECT_DETECTOR,
    DEFAULT_LABEL_PATH,
    DEFAULT_MAX_DETECTIONS,
    DEFAULT_MODEL_PATH,
    DEFAULT_MULTI_PROCESS_SERVICE,
    DESC_COMPONENT,
    DESC_LABEL_PATH,
    DESC_MAX_DETECTIONS,
    DESC_MODEL_PATH,
    DESC_MULTI_PROCESS_SERVICE,
    DESC_OBJECT_DETECTOR,
)
from .hailo_process import Hailo8Work

if TYPE_CHECKING:
    import numpy as np

    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

OBJECT_DETECTOR_SCHEMA = OBJECT_DETECTOR_BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_MODEL_PATH,
            default=DEFAULT_MODEL_PATH,
            description=DESC_MODEL_PATH,
        ): Maybe(str, vol.Any(PathExists(), Url())),
        vol.Optional(
            CONFIG_LABEL_PATH,
            default=DEFAULT_LABEL_PATH,
            description=DESC_LABEL_PATH,
        ): str,
        vol.Optional(
            CONFIG_MAX_DETECTIONS,
            default=DEFAULT_MAX_DETECTIONS,
            description=DESC_MAX_DETECTIONS,
        ): int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            {
                vol.Optional(
                    CONFIG_MULTI_PROCESS_SERVICE,
                    default=DEFAULT_MULTI_PROCESS_SERVICE,
                    description=DESC_MULTI_PROCESS_SERVICE,
                ): bool,
                vol.Required(
                    CONFIG_OBJECT_DETECTOR, description=DESC_OBJECT_DETECTOR
                ): OBJECT_DETECTOR_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, _config: dict[str, Any]) -> bool:
    """Set up hailo component."""
    vis.data[COMPONENT] = {}
    return True


def setup_domains(vis: Viseron, config: dict[str, Any]) -> None:
    """Set up hailo domains."""
    config = config[COMPONENT]

    if config.get(CONFIG_OBJECT_DETECTOR, None):
        for camera_identifier in config[CONFIG_OBJECT_DETECTOR][CONFIG_CAMERAS]:
            setup_domain(
                vis,
                COMPONENT,
                CONFIG_OBJECT_DETECTOR,
                config,
                identifier=camera_identifier,
                require_domains=[
                    RequireDomain(
                        domain="camera",
                        identifier=camera_identifier,
                    )
                ],
            )


def unload(vis: Viseron) -> None:
    """Unload hailo component."""
    vis.data.pop(COMPONENT, None)


class LoadHailo8Error(ViseronError):
    """Error raised on all failures to load Hailo8."""


class Hailo8Detector(ChildProcessWorker):
    """Hailo 8 object detector."""

    def __init__(self, vis: Viseron, config: dict[str, Any]) -> None:
        self._config = config
        hailo_arch = get_hailo_arch()
        LOGGER.debug(f"Detected Hailo architecture: {hailo_arch}")

        if hailo_arch is None:
            LOGGER.error("Failed to detect Hailo architecture.")
            raise ComponentNotReady

        self.model_path = get_model(
            config[CONFIG_OBJECT_DETECTOR][CONFIG_MODEL_PATH], hailo_arch
        )
        self.labels = load_labels(config[CONFIG_OBJECT_DETECTOR][CONFIG_LABEL_PATH])

        self._result_queues: dict[str, Queue] = {}
        mp_context = get_child_process_context()
        self._process_initialization_done = mp_context.Event()
        self._process_initialization_error = mp_context.Event()
        self._model_height: int
        self._model_width: int

        super().__init__(
            vis,
            f"{COMPONENT}.{CONFIG_OBJECT_DETECTOR}",
            Hailo8Work(
                self.model_path,
                config[CONFIG_MULTI_PROCESS_SERVICE],
                self._process_initialization_done,
                self._process_initialization_error,
            ),
        )
        self.initialize()

    def initialize(self) -> None:
        """Initialize Hailo8."""
        self._process_initialization_done.wait(30)
        if (
            not self._process_initialization_done.is_set()
            or self._process_initialization_error.is_set()
        ):
            LOGGER.error("Failed to load Hailo8")
            self.stop()
            raise LoadHailo8Error

        self._model_size_event = mp.Event()
        self._model_width = 0
        self._model_height = 0
        get_model_size(self._process_queue)
        self._model_size_event.wait(10)
        if not self._model_size_event.is_set():
            LOGGER.error("Failed to get model size")
            self.stop()
            raise LoadHailo8Error("Failed to get model size")
        LOGGER.debug(f"Model size: {self._model_width}x{self._model_height}")

    def work_output(self, item) -> None:
        """Put result into queue."""
        if item.get("get_model_size", None):
            self._model_width = item["get_model_size"]["model_width"]
            self._model_height = item["get_model_size"]["model_height"]
            self._model_size_event.set()
            return

        pop_if_full(self._result_queues[item["camera_identifier"]], item)

    def preprocess(self, frame):
        """Pre process frame before detection."""
        return letterbox_resize(frame, self.model_width, self.model_height)

    def detect(
        self,
        frame: np.ndarray,
        camera_identifier: str,
        result_queue: Queue,
    ):
        """Perform detection."""
        self._result_queues[camera_identifier] = result_queue
        pop_if_full(
            self.input_queue,
            {
                "frame": frame,
                "camera_identifier": camera_identifier,
            },
        )
        try:
            item = result_queue.get(timeout=3)
        except Empty:
            return None
        return item["result"]

    def post_process(
        self,
        detections,
        camera_resolution: tuple[int, int],
        min_confidence: float,
        max_boxes: int = 50,
    ) -> list[DetectedObject]:
        """Post process detections."""
        all_detections = []
        for class_id, detection in enumerate(detections):
            for det in detection:
                bbox, score = det[:4], det[4]
                if score >= min_confidence:
                    all_detections.append((class_id, score, bbox))

        # Sort all detections by score descending
        all_detections.sort(reverse=True, key=lambda x: x[1])

        # Filter to max_boxes highest scoring detections
        top_detections = all_detections[:max_boxes]
        _detections = []
        for class_id, score, bbox in top_detections:
            _detections.append(
                DetectedObject.from_relative_letterboxed(
                    self.labels[int(class_id)],
                    score,
                    bbox[1],
                    bbox[0],
                    bbox[3],
                    bbox[2],
                    frame_res=camera_resolution,
                    model_res=self.model_res,
                )
            )

        return _detections

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._model_height

    @property
    def model_res(self):
        """Return trained model resolution."""
        return self.model_width, self.model_height
