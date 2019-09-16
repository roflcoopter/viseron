from apscheduler.schedulers.background import BackgroundScheduler
from path import Path
import logging
import config
import time

LOGGER = logging.getLogger(__name__)


class Cleanup(object):
    def __init__(self):
        self.directory = config.OUTPUT_DIRECTORY

        if config.DAYS_TO_RETAIN is None:
            self.days_to_retain = 7
            LOGGER.error("Number of days to retain recordings "
                         "is not specified. Default = 7")
        else:
            self.days_to_retain = config.DAYS_TO_RETAIN

        self.scheduler = BackgroundScheduler(timezone="UTC")
        self.scheduler.add_job(self.cleanup, 'cron', hour='1')
        return

    def cleanup(self):
        LOGGER.debug("Running cleanup")
        retention_period = time.time() - (self.days_to_retain * 24 * 60 * 60)
        d = Path(self.directory)

        files = d.walkfiles("*.mp4")
        for file in files:
            if file.mtime <= retention_period:
                LOGGER.info("Removing {}".format(file))
                file.remove()

        folders = d.walkdirs("*-*-*")
        for folder in folders:
            LOGGER.debug("Items in {}: {}".format(folder,
                                                  len(folder.listdir())))
            if len(folder.listdir()) == 0:
                try:
                    folder.rmdir()
                    LOGGER.info("Removing {}".format(folder))
                except OSError:
                    LOGGER.error("Could not remove {}".format(folder))
