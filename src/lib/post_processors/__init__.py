import importlib
import logging
from queue import Queue
from threading import Thread
from typing import Dict


from lib.config.config_logging import LoggingConfig
from lib.config.config_post_processors import PostProcessorsConfig

LOGGER = logging.getLogger(__name__)


class PostProcessor:
    def __init__(self, config, processor_type, processor_config):
        if getattr(config.logging, "level", None):
            LOGGER.setLevel(config.logging.level)

        LOGGER.debug(f"Initializing post processor {processor_type}")
        processor = self.import_processor(processor_type, processor_config)
        config = processor.Config(config, processor.SCHEMA(processor_config))
        self.input_queue = Queue(maxsize=10)
        self._post_processor = processor.Processor(config)

        processor_thread = Thread(target=self.post_process)
        processor_thread.daemon = True
        processor_thread.start()

        LOGGER.debug(f"Post processor {processor_type} initialized")

    @staticmethod
    def import_processor(processor_type, processor_config):
        return importlib.import_module(
            "lib.post_processors." + processor_type + "." + processor_config["type"]
        )

    def post_process(self):
        while True:
            frame = self.input_queue.get()
            self._post_processor.process(frame["frame"], frame["object"])


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
