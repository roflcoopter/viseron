"""Interface to different post processors."""
from __future__ import annotations

import importlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from queue import Queue
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, Union

from voluptuous import Required, Schema

from viseron.const import TOPIC_FRAME_SCAN_POSTPROC
from viseron.data_stream import DataStream
from viseron.exceptions import PostProcessorImportError, PostProcessorStructureError
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron.camera.frame import Frame
    from viseron.config import NVRConfig, ViseronConfig
    from viseron.detector.detected_object import DetectedObject
    from viseron.zones import Zone


SCHEMA = Schema(
    {
        Required("type"): str,
    }
)


LOGGER = logging.getLogger(__name__)


@dataclass
class PostProcessorFrame:
    """Object representing a frame that is passed to post processors."""

    camera_config: NVRConfig
    frame: Frame
    detected_object: DetectedObject
    zone: Union[Zone, None] = None


class AbstractProcessorConfig(ABC):
    """Abstract Processor Config."""

    SCHEMA = SCHEMA

    def __init__(self, processor_config: Dict[str, Any]):
        pass


class AbstractProcessor(ABC):
    """Abstract Processor."""

    def __init__(
        self,
        config: ViseronConfig,
        processor_config: AbstractProcessorConfig,
    ):
        pass

    @abstractmethod
    def process(self, frame_to_process: PostProcessorFrame):
        """Process frame."""


class PostProcessor:
    """Subscribe to frames and run post processor using the configured processor."""

    post_processor_list: list = []

    def __init__(
        self,
        config: ViseronConfig,
        processor_type: str,
        processor_config: Dict[str, Any],
    ):
        processor = self.import_processor(processor_type, processor_config)
        self._post_processor = processor.Processor(  # type: ignore
            config,
            processor.Config(  # type: ignore
                processor.SCHEMA(processor_config),  # type: ignore
            ),
        )

        self._topic_scan = f"*/{TOPIC_FRAME_SCAN_POSTPROC}/{processor_type}"
        self._post_processor_queue: Queue = Queue(maxsize=10)
        processor_thread = RestartableThread(
            name=__name__, target=self.post_process, daemon=True, register=True
        )
        processor_thread.start()
        DataStream.subscribe_data(self._topic_scan, self._post_processor_queue)

        self.post_processor_list.append(self)
        LOGGER.debug(f"Post processor {processor_type} initialized")

    @staticmethod
    def import_processor(
        processor_type: str, processor_config: Dict[str, Any]
    ) -> ModuleType:
        """Import processor dynamically."""
        LOGGER.debug(f"Initializing post processor {processor_type}")
        try:
            post_processor_module = importlib.import_module(
                f"viseron.post_processors.{processor_type}.{processor_config['type']}"
            )
        except ModuleNotFoundError as error:
            raise PostProcessorImportError(processor_config["type"]) from error
        LOGGER.debug("Successfully imported post processor")

        if hasattr(post_processor_module, "Processor") and issubclass(
            post_processor_module.Processor, AbstractProcessor  # type: ignore
        ):
            pass
        else:
            raise PostProcessorStructureError(processor_config["type"])

        return post_processor_module

    def post_process(self):
        """Post processor loop."""
        while True:
            frame_to_process: PostProcessorFrame = self._post_processor_queue.get()
            self._post_processor.process(frame_to_process)

    def on_connect(self):
        """On established MQTT connection."""
        if getattr(self._post_processor, "on_connect", None):
            self._post_processor.on_connect()
