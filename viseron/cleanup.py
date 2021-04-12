"""Cleanup no longer needed files."""
import datetime
import logging
import os
import time

from apscheduler.schedulers.background import BackgroundScheduler
from path import Path

from viseron.const import CAMERA_SEGMENT_DURATION

LOGGER = logging.getLogger(__name__)
logging.getLogger("apscheduler.scheduler").setLevel(logging.ERROR)
logging.getLogger("apscheduler.executors").setLevel(logging.ERROR)


class Cleanup:
    """Removes old recordings on a schedule."""

    def __init__(self, config):
        self._config = config
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._scheduler.add_job(self.cleanup, "cron", hour="1")

    def cleanup(self):
        """Delete all recordings that have past the configured days to retain."""
        LOGGER.debug("Running cleanup")
        retention_period = time.time() - (self._config.recorder.retain * 24 * 60 * 60)
        dirs = Path(self._config.recorder.folder)

        extensions = [f"*.{self._config.recorder.extension}", "*.jpg"]
        for extension in extensions:
            files = dirs.walkfiles(extension)
            for file in files:
                if file.mtime <= retention_period:
                    LOGGER.debug(f"Removing file {file}")
                    file.remove()

        folders = dirs.walkdirs("*-*-*")
        for folder in folders:
            LOGGER.debug(f"Items in {folder}: {len(folder.listdir())}")
            for subdir in folder.listdir():
                if os.path.isdir(subdir) and len(subdir.listdir()) == 0:
                    try:
                        os.rmdir(subdir)
                        LOGGER.debug(f"Removing directory {subdir}")
                    except OSError:
                        LOGGER.error(f"Could not remove directory {subdir}")

            if len(folder.listdir()) == 0:
                try:
                    folder.rmdir()
                    LOGGER.debug(f"Removing directory {folder}")
                except OSError:
                    LOGGER.error(f"Could not remove directory {folder}")

    def start(self):
        """Start the scheduler."""
        self._scheduler.start()


class SegmentCleanup:
    """Clean up segments created by FFmpeg."""

    def __init__(self, config):
        self._directory = os.path.join(
            config.recorder.segments_folder, config.camera.name
        )
        # Make sure we dont delete a segment which is needed by recorder
        self._max_age = config.recorder.lookback + (CAMERA_SEGMENT_DURATION * 3)
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._scheduler.add_job(
            self.cleanup,
            "interval",
            seconds=CAMERA_SEGMENT_DURATION,
            id="segment_cleanup",
        )
        self._scheduler.start()

    def cleanup(self):
        """Delete all segments that are no longer needed."""
        now = datetime.datetime.now().timestamp()
        for segment in os.listdir(self._directory):
            start_time = datetime.datetime.strptime(
                segment.split(".")[0], "%Y%m%d%H%M%S"
            ).timestamp()
            if now - start_time > self._max_age:
                os.remove(os.path.join(self._directory, segment))

    def start(self):
        """Start the scheduler."""
        LOGGER.debug("Starting segment cleanup")
        self._scheduler.start()

    def pause(self):
        """Pauise the scheduler."""
        LOGGER.debug("Pausing segment cleanup")
        self._scheduler.pause_job("segment_cleanup")

    def resume(self):
        """Resume the scheduler."""
        LOGGER.debug("Resuming segment cleanup")
        self._scheduler.resume_job("segment_cleanup")
