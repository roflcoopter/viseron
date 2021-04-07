import importlib
import logging
from queue import Queue
from threading import Thread
from typing import Dict

from viseron.config import ViseronConfig
from viseron.config.config_logging import LoggingConfig
from viseron.config.config_post_processors import PostProcessorsConfig
from viseron.const import TOPIC_FRAME_SCAN_POSTPROC_FACEREC
from viseron.data_stream import DataStream

LOGGER = logging.getLogger(__name__)


class PostProcessor:
    post_processor_list: list = []

    def __init__(
        self, config: ViseronConfig, processor_type, processor_config, mqtt_queue
    ):
        self.post_processor_list.append(self)
        if getattr(config.post_processors.logging, "level", None):
            LOGGER.setLevel(config.post_processors.logging.level)

        LOGGER.debug(f"Initializing post processor {processor_type}")
        processor = self.import_processor(processor_type, processor_config)
        LOGGER.debug("Successfully imported post processor")
        self._post_processor = processor.Processor(
            config,
            processor.Config(
                config.post_processors, processor.SCHEMA(processor_config)
            ),
            mqtt_queue,
        )

        self._topic_scan = f"*/{TOPIC_FRAME_SCAN_POSTPROC_FACEREC}"
        self._post_processor_queue: Queue = Queue(maxsize=10)
        processor_thread = Thread(target=self.post_process)
        processor_thread.daemon = True
        processor_thread.start()
        DataStream.subscribe_data(self._topic_scan, self._post_processor_queue)

        LOGGER.debug(f"Post processor {processor_type} initialized")

    @staticmethod
    def import_processor(processor_type, processor_config):
        return importlib.import_module(
            f"viseron.post_processors.{processor_type}.{processor_config['type']}"
        )

    def post_process(self):
        while True:
            data = self._post_processor_queue.get()
            self._post_processor.process(
                data["camera_config"], data["frame"], data["object"], data["zone"]
            )

    def on_connect(self, client):
        if getattr(self._post_processor, "on_connect", None):
            self._post_processor.on_connect(client)


class PostProcessorConfig:
    """Base config class for all post processors.
    Each post processor has to have a Config class which inherits this class
    """

    def __init__(
        self, post_processors_config: PostProcessorsConfig, processor_config: Dict
    ):
        self._logging = getattr(post_processors_config, "logging", None)
        if processor_config.get("logging", None):
            self._logging = LoggingConfig(processor_config["logging"])

    @property
    def logging(self):
        return self._logging
