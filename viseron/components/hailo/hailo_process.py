"""Hailo 8 object detection, executed in a child process.

Deliberately depends on nothing that reaches back into the running Viseron instance,
so that the child process can be created with the forkserver start method to reduce
memory usage.
"""

from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING

import numpy as np
from hailo_platform import HEF, FormatType, HailoSchedulingAlgorithm, VDevice
from hailo_platform.pyhailort.pyhailort import AsyncInferJob, FormatOrder

from viseron.components.hailo.utils import (
    LOGGER as UTILS_LOGGER,
    inference_callback,
)
from viseron.helpers.child_process_worker import ChildProcessWork

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event

LOGGER = logging.getLogger(__name__)


class Hailo8Work(ChildProcessWork):
    """Run Hailo 8 inference inside the child process."""

    def __init__(
        self,
        model_path: str,
        multi_process_service: bool,
        initialization_done: Event,
        initialization_error: Event,
    ) -> None:
        self._model_path = model_path
        self._multi_process_service = multi_process_service
        self._initialization_done = initialization_done
        self._initialization_error = initialization_error
        self._hailo_inference: HailoInfer

    @property
    def logger_names(self) -> tuple[str, ...]:
        """Return the names of the loggers the work uses in the child process."""
        return (LOGGER.name, UTILS_LOGGER.name)

    def initialize(self) -> None:
        """Load network inside the child process."""
        try:
            self._hailo_inference = HailoInfer(
                self._model_path,
                multi_process_service=self._multi_process_service,
            )
        except Exception as error:  # pylint: disable=broad-except
            LOGGER.error(f"Failed to load Hailo8: {error}")
            self._initialization_error.set()
        self._initialization_done.set()

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


class HailoInfer:
    """Helper around Hailo SDK to perform asynchronous inference.

    Based on:
    https://raw.githubusercontent.com/hailo-ai/Hailo-Application-Code-Examples/refs/heads/main/runtime/hailo-8/python/common/hailo_inference.py # noqa: E501
    """  # noqa: E501

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
