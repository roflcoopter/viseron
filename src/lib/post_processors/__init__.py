import importlib
import logging
from queue import Queue
from threading import Thread

from lib.config.config_logging import LoggingConfig

LOGGER = logging.getLogger(__name__)


class PostProcessor:
    def __init__(self, processor_type, processor_config):
        LOGGER.debug(f"Initializing post processor {processor_type}")
        processor = self.import_processor(processor_type, processor_config)
        config = processor.Config(processor.SCHEMA(processor_config))
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
    Each post processor has to have a Config class which inherits this class"""

    def __init__(self, post_processor):
        self._logging = None
        if post_processor.get("logging", None):
            self._logging = LoggingConfig(post_processor["logging"])

    @property
    def logging(self):
        return self._logging
