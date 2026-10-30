"""Native Darknet object detection, executed in a child process.

Deliberately depends on nothing that reaches back into the running Viseron instance,
so that the child process can be created with the forkserver start method to reduce
memory usage.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from viseron.helpers.child_process_worker import ChildProcessWork
from viseron.helpers.logs import CTypesLogPipe

from . import darknet

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event

LIBDARKNET_LOGGER_NAME = "viseron.components.darknet.libdarknet"


class DarknetNativeWork(ChildProcessWork):
    """Run native Darknet detections inside the child process."""

    def __init__(
        self,
        half_precision: bool,
        model_config: str,
        data_path: str,
        model_path: str,
        model_width: int,
        model_height: int,
        initialization_done: Event,
    ) -> None:
        self._half_precision = half_precision
        self._model_config = model_config
        self._data_path = data_path
        self._model_path = model_path
        self._model_width = model_width
        self._model_height = model_height
        self._initialization_done = initialization_done
        self._darknet: darknet.DarknetWrapper
        self._network: Any
        self._labels: Any
        self._darknet_image: Any

    @property
    def logger_names(self) -> tuple[str, ...]:
        """Return the names of the loggers the work uses in the child process."""
        return (LIBDARKNET_LOGGER_NAME,)

    def initialize(self) -> None:
        """Load the Darknet library and network inside the child process."""
        self._darknet = darknet.DarknetWrapper(self._half_precision)
        self._darknet_image = self._darknet.make_image(
            self._model_width, self._model_height, 3
        )

        logger = logging.getLogger(LIBDARKNET_LOGGER_NAME)
        logpipe = CTypesLogPipe(logger, logging.DEBUG, 1)
        self._network, self._labels = self._darknet.load_network(
            self._model_config,
            self._data_path,
            self._model_path,
            batch_size=1,
        )
        logpipe.close()
        self._initialization_done.set()

    def _detect(self, frame: bytes, min_confidence: float) -> list:
        """Run detection on frame."""
        self._darknet.copy_image_from_bytes(self._darknet_image, frame)
        return self._darknet.detect_image(
            self._network,
            self._labels,
            self._darknet_image,
            thresh=min_confidence,
        )

    def work_input(self, item: dict[str, Any]) -> dict[str, Any]:
        """Perform object detection."""
        item["result"] = self._detect(item["frame"], item["min_confidence"])
        return item
