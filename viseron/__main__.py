""" Start Viseron """
import logging

from viseron import Viseron
from viseron.helpers.logs import DuplicateFilter, ViseronLogFormat

LOGGER = logging.getLogger()


def log_settings():
    """Set custom log settings."""
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)-12s] [%(levelname)-8s] - %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    formatter = ViseronLogFormat()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(DuplicateFilter())
    LOGGER.addHandler(handler)


def main():
    """Start Viseron."""
    log_settings()
    Viseron()


if __name__ == "__main__":
    main()
