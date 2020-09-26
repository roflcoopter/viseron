import logging

from voluptuous import Optional

from lib.post_processors import PostProcessorConfig
from lib.post_processors.schema import SCHEMA as BASE_SCHEMA

from .defaults import MODEL_PATH

SCHEMA = BASE_SCHEMA.extend({Optional("model_path", default=MODEL_PATH): str,})

LOGGER = logging.getLogger(__name__)


class Processor:
    def __init__(self, config):
        LOGGER.debug("Initializing dlib")

    def process(self, frame):
        LOGGER.debug(f"Processing {frame}")


class Config(PostProcessorConfig):
    def __init__(self, processor_config):
        super().__init__(processor_config)
        self._model_path = processor_config["model_path"]

    @property
    def model_path(self):
        return self._model_path
