import logging

LOGGER = logging.getLogger(__name__)


class Processor:
    def __init__(self):
        LOGGER.debug("Initializing dlib")

    def process(self, frame):
        LOGGER.debug(f"Processing {frame}")
