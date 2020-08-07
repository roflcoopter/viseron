import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from path import Path

LOGGER = logging.getLogger(__name__)


class Cleanup:
    def __init__(self, config):
        self.directory = config.recorder.folder

        if config.recorder.retain is None:
            self.days_to_retain = 7
            LOGGER.error(
                "Number of days to retain recordings is not specified. Defaulting to 7"
            )
        else:
            self.days_to_retain = config.recorder.retain

        self.scheduler = BackgroundScheduler(timezone="UTC")
        self.scheduler.add_job(self.cleanup, "cron", hour="1")

    def cleanup(self):
        LOGGER.debug("Running cleanup")
        retention_period = time.time() - (self.days_to_retain * 24 * 60 * 60)
        dirs = Path(self.directory)

        extensions = ["*.mp4", "*.jpg"]
        for extension in extensions:
            files = dirs.walkfiles(extension)
            for file in files:
                if file.mtime <= retention_period:
                    LOGGER.info(f"Removing {file}")
                    file.remove()

        folders = dirs.walkdirs("*-*-*")
        for folder in folders:
            LOGGER.debug(f"Items in {folder}: {len(folder.listdir())}")
            if len(folder.listdir()) == 0:
                try:
                    folder.rmdir()
                    LOGGER.info(f"Removing {folder}")
                except OSError:
                    LOGGER.error(f"Could not remove {folder}")
