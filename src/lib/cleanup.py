import datetime
import logging
import os
import time

from apscheduler.schedulers.background import BackgroundScheduler
from const import CAMERA_SEGMENT_DURATION
from path import Path

LOGGER = logging.getLogger(__name__)
logging.getLogger("apscheduler.scheduler").setLevel(logging.ERROR)
logging.getLogger("apscheduler.executors").setLevel(logging.ERROR)


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

        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._scheduler.add_job(self.cleanup, "cron", hour="1")

    def cleanup(self):
        LOGGER.debug("Running cleanup")
        retention_period = time.time() - (self.days_to_retain * 24 * 60 * 60)
        dirs = Path(self.directory)

        extensions = ["*.mp4", "*.jpg"]
        for extension in extensions:
            files = dirs.walkfiles(extension)
            for file in files:
                if file.mtime <= retention_period:
                    LOGGER.debug(f"Removing {file}")
                    file.remove()

        folders = dirs.walkdirs("*-*-*")
        for folder in folders:
            LOGGER.debug(f"Items in {folder}: {len(folder.listdir())}")
            if len(folder.listdir()) == 0:
                try:
                    folder.rmdir()
                    LOGGER.debug(f"Removing {folder}")
                except OSError:
                    LOGGER.error(f"Could not remove {folder}")

    def start(self):
        self._scheduler.start()


class SegmentCleanup:
    def __init__(self, config):
        self._directory = os.path.join(
            config.recorder.segments_folder, config.camera.name
        )
        # Make sure we dont delete a segment which is needed by recorder
        self._max_age = (
            (int(config.recorder.lookback / 2) * 3) + CAMERA_SEGMENT_DURATION + 1
        )
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._scheduler.add_job(
            self.cleanup, "interval", seconds=10, id="segment_cleanup"
        )
        self._scheduler.start()

    def cleanup(self):
        now = datetime.datetime.now().timestamp()
        for segment in os.listdir(self._directory):
            start_time = datetime.datetime.strptime(
                segment.split(".")[0], "%Y%m%d%H%M%S"
            ).timestamp()
            if now - start_time > self._max_age:
                os.remove(os.path.join(self._directory, segment))

    def start(self):
        self._scheduler.start()

    def pause(self):
        self._scheduler.pause_job("segment_cleanup")

    def resume(self):
        self._scheduler.resume_job("segment_cleanup")
