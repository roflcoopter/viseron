import importlib
import logging
from queue import Queue
from threading import Thread

LOGGER = logging.getLogger(__name__)


class PostProcessor:
    def __init__(self, processor_type, processor_config):
        LOGGER.debug(f"Initializing post processor {processor_type}")
        processor = self.import_processor(processor_type, processor_config)
        self.input_queue = Queue(maxsize=10)
        self._post_processor = processor.Processor()

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
            self._post_processor.process(self.input_queue.get())
