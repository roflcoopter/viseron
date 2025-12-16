"""Hailo component."""

from __future__ import annotations

import logging
import multiprocessing as mp
from functools import partial
from queue import Empty, Queue
from typing import Any

import numpy as np
import voluptuous as vol
from hailo_platform import HEF, FormatType, HailoSchedulingAlgorithm, VDevice
from hailo_platform.pyhailort.pyhailort import AsyncInferJob, FormatOrder

from viseron import Viseron
from viseron.components.hailo.utils import (
    get_hailo_arch,
    get_model,
    get_model_size,
    inference_callback,
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


def setup(vis: Viseron, config: dict[str, Any]) -> bool:
    """Set up Hailo component."""
    config = config[COMPONENT]

    try:
        vis.data[COMPONENT] = Hailo8Detector(vis, config)
    except Exception as error:
        LOGGER.error("Failed to start Hailo 8 detector: %s", error, exc_info=True)
        raise ComponentNotReady from error

    if config.get(CONFIG_OBJECT_DETECTOR, None):
        for camera_identifier in config[CONFIG_OBJECT_DETECTOR][CONFIG_CAMERAS].keys():
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

    return True


class LoadHailo8Error(ViseronError):
    """Error raised on all failures to load Hailo8."""


class Hailo8Detector(ChildProcessWorker):
    """Hailo 8 object detector."""

    def __init__(self, vis: Viseron, config: dict[str, Any]):
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
        self._process_initialization_done = mp.Event()
        self._process_initialization_error = mp.Event()
        self._hailo_inference: HailoInfer
        self._model_height: int
        self._model_width: int

        self._process_initialization_done = mp.Event()
        super().__init__(vis, f"{COMPONENT}.{CONFIG_OBJECT_DETECTOR}")
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

    def process_initialization(self) -> None:
        """Load network inside the child process."""
        try:
            self._hailo_inference = HailoInfer(
                self.model_path,
                multi_process_service=self._config[CONFIG_MULTI_PROCESS_SERVICE],
            )
            (
                self._model_height,
                self._model_width,
                _,
            ) = self._hailo_inference.get_input_shape()
        except Exception as error:  # pylint: disable=broad-except
            LOGGER.error(f"Failed to load Hailo8: {error}")
            self._process_initialization_error.set()
        self._process_initialization_done.set()

    def work_input(self, item):
        """Perform object detection."""
        if item == "get_model_size":
            height, width, _ = self._hailo_inference.get_input_shape()
            return {
                "get_model_size": {
                    "model_width": width,
                    "model_height": height,
                }
            }

        # Run async inference
        inference_callback_fn = partial(inference_callback, item=item)
        async_job = self._hailo_inference.run([item["frame"]], inference_callback_fn)
        async_job.wait(3000)
        return item

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


class HailoInfer:
    """Helper around Hailo SDK to perform asynchronous inference.

    Based on https://raw.githubusercontent.com/hailo-ai/Hailo-Application-Code-Examples/refs/heads/main/runtime/hailo-8/python/common/hailo_inference.py #pylint: disable=line-too-long
    """

    def __init__(
        self,
        hef_path: str,
        batch_size: int = 1,
        input_type: str | None = None,
        output_type: str | None = None,
        priority: int | None = 0,
        multi_process_service: bool = True,
    ) -> None:
        """Initialize async inference wrapper for a HEF model."""
        params = VDevice.create_params()
        # Set the scheduling algorithm to round-robin to activate the scheduler
        params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
        if multi_process_service:
            params.multi_process_service = True
        params.group_id = "SHARED"
        vdev = VDevice(params)

        self.target = vdev
        self.hef = HEF(hef_path)

        self.infer_model = self.target.create_infer_model(hef_path)
        self.infer_model.set_batch_size(batch_size)

        self._set_input_type(input_type)
        self._set_output_type(output_type)

        self.config_ctx = self.infer_model.configure()
        self.configured_model = self.config_ctx.__enter__()
        self.configured_model.set_scheduler_priority(priority)
        self.last_infer_job: AsyncInferJob | None = None

    def _set_input_type(self, input_type: str | None = None) -> None:
        """Set the input type for the HEF model. If the model has multiple inputs."""
        if input_type is not None:
            self.infer_model.input().set_format_type(getattr(FormatType, input_type))

    def _set_output_type(self, output_type: str | None = None) -> None:
        """Set the output type for each model output."""
        self.nms_postprocess_enabled = False

        # If the model uses HAILO_NMS_WITH_BYTE_MASK format (e.g.,instance segmentation)
        if (
            self.infer_model.outputs[0].format.order
            == FormatOrder.HAILO_NMS_WITH_BYTE_MASK
        ):
            # Use UINT8 and skip setting output formats
            self.nms_postprocess_enabled = True
            self.output_type = self._output_data_type2dict("UINT8")
            return

        # Otherwise, set the format type based on the provided output_type argument
        self.output_type = self._output_data_type2dict(output_type)

        # Apply format to each output layer
        for name, dtype in self.output_type.items():
            self.infer_model.output(name).set_format_type(getattr(FormatType, dtype))

    def get_input_shape(self) -> tuple[int, ...]:
        """Get the shape of the model's input layer."""
        return self.hef.get_input_vstream_infos()[0].shape  # Assumes one input

    def run(self, input_batch: list[np.ndarray], inference_callback_fn):
        """Run an asynchronous inference job on a batch of preprocessed inputs."""
        bindings_list = self.create_bindings(self.configured_model, input_batch)
        self.configured_model.wait_for_async_ready(timeout_ms=10000)

        # Launch async inference and attach the result handler
        self.last_infer_job = self.configured_model.run_async(
            bindings_list, partial(inference_callback_fn, bindings_list=bindings_list)
        )
        return self.last_infer_job

    def create_bindings(self, configured_model, input_batch):
        """Create a list of input-output bindings for a batch of frames."""

        def frame_binding(frame: np.ndarray):
            output_buffers = {
                name: np.empty(
                    self.infer_model.output(name).shape,
                    dtype=(getattr(np, self.output_type[name].lower())),
                )
                for name in self.output_type
            }

            binding = configured_model.create_bindings(output_buffers=output_buffers)
            binding.input().set_buffer(np.array(frame))
            return binding

        return [frame_binding(frame) for frame in input_batch]

    def _output_data_type2dict(self, data_type: str | None) -> dict[str, str]:
        """Generate a dictionary mapping for output layer data types."""
        valid_types = {"float32", "uint8", "uint16"}
        data_type_dict = {}

        for output_info in self.hef.get_output_vstream_infos():
            name = output_info.name
            if data_type is None:
                # Extract type from HEF metadata
                hef_type = str(output_info.format.type).rsplit(".", maxsplit=1)[-1]
                data_type_dict[name] = hef_type
            else:
                if data_type.lower() not in valid_types:
                    raise ValueError(
                        f"Invalid data_type: {data_type}. Must be one of {valid_types}"
                    )
                data_type_dict[name] = data_type

        return data_type_dict
