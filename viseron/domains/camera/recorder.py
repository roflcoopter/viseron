"""Base recorder."""
from __future__ import annotations

import datetime
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler
from path import Path

from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.helpers import create_directory, draw_objects

from .const import (
    CONFIG_EXTENSION,
    CONFIG_FILENAME_PATTERN,
    CONFIG_FOLDER,
    CONFIG_IDLE_TIMEOUT,
    CONFIG_RECORDER,
    CONFIG_RETAIN,
    CONFIG_SAVE_TO_DISK,
    CONFIG_THUMBNAIL,
    EVENT_RECORDER_START,
    EVENT_RECORDER_STOP,
)
from .entity.binary_sensor import RecorderBinarySensor
from .entity.image import ThumbnailImage
from .shared_frames import SharedFrame

if TYPE_CHECKING:
    from . import AbstractCamera


@dataclass
class EventRecorderStart:
    """Hold information on recorder start event."""

    start_time: datetime.datetime
    path: str
    thumbnail: np.ndarray
    thumbnail_path: str | None
    objects: list[DetectedObject]


@dataclass
class EventRecorderStop:
    """Hold information on recorder stop event."""

    start_time: datetime.datetime
    end_time: datetime.datetime
    path: str
    thumbnail_path: str | None


class AbstractRecorder(ABC):
    """Abstract recorder."""

    def __init__(self, vis, component, config, camera):
        self._logger = logging.getLogger(self.__module__ + "." + camera.identifier)
        self._vis = vis
        self._config = config
        self._camera: AbstractCamera = camera

        self.is_recording = False
        self._last_recording_path = None
        self._last_recording_thumbnail_path = None
        self._last_recording_start = None
        self._last_recording_end = None
        self._extensions = list(
            {
                f"*.{self._config[CONFIG_RECORDER][CONFIG_EXTENSION]}",
                "*.mp4",
                "*.mkv",
            }
        )

        self.recordings_folder = os.path.join(
            self._config[CONFIG_RECORDER][CONFIG_FOLDER], self._camera.identifier
        )
        create_directory(self.recordings_folder)

        self._scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
        self._scheduler.add_job(self.cleanup_recordings, "cron", hour="1")
        self._scheduler.start()
        self.cleanup_recordings()

        vis.add_entity(component, RecorderBinarySensor(vis, self._camera))
        vis.add_entity(component, ThumbnailImage(vis, self._camera))

    def as_dict(self):
        """Return recorder information as dict."""
        recordings_dict = {}
        dirs = Path(self.recordings_folder)
        date_folders = dirs.walkdirs("*-*-*")
        for date_folder in date_folders:
            if len(date_folder.listdir()) == 0:
                continue

            daily_recordings = {}
            for extension in self._extensions:
                recordings = date_folder.walkfiles(extension)
                for recording in recordings:
                    daily_recordings[str(recording.name)] = {
                        "path": str(recording),
                        "date": str(date_folder.name),
                        "filename": str(recording.name),
                        "thumbnail_path": os.path.join(
                            date_folder, f"{str(recording.stem)}.jpg"
                        ),
                    }
            recordings_dict[date_folder.name] = daily_recordings
        return recordings_dict

    @staticmethod
    def subfolder_name(today):
        """Generate name of folder for recording."""
        return f"{today.year:04}-{today.month:02}-{today.day:02}"

    def create_thumbnail(self, file_name, frame, objects, resolution):
        """Create thumbnails, sent to MQTT and/or saved to disk based on config."""
        draw_objects(
            frame,
            objects,
            resolution,
        )
        cv2.imwrite(file_name, frame)

        if self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_SAVE_TO_DISK]:
            thumbnail_folder = os.path.join(
                self._config[CONFIG_RECORDER][CONFIG_FOLDER],
                "thumbnails",
                self._camera.name,
            )
            create_directory(thumbnail_folder)

            self._logger.debug(f"Saving thumbnail in {thumbnail_folder}")
            if not cv2.imwrite(
                os.path.join(thumbnail_folder, "latest_thumbnail.jpg"),
                frame,
            ):
                self._logger.error("Failed saving thumbnail to disk")
        return frame

    def start(
        self,
        shared_frame: SharedFrame,
        objects_in_fov: list[DetectedObject],
        resolution,
    ):
        """Start recording."""
        self._logger.info("Starting recorder")
        self.is_recording = True
        self._last_recording_start = datetime.datetime.now()
        self._last_recording_end = None

        if self._config[CONFIG_RECORDER][CONFIG_FOLDER] is None:
            self._logger.error("Output directory is not specified")
            return

        # Create filename
        filename_pattern = self.last_recording_start.strftime(
            self._config[CONFIG_RECORDER][CONFIG_FILENAME_PATTERN]
        )
        video_name = (
            f"{filename_pattern}.{self._config[CONFIG_RECORDER][CONFIG_EXTENSION]}"
        )
        thumbnail_name = self.last_recording_start.strftime(
            self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_FILENAME_PATTERN]
        )
        thumbnail_name = f"{thumbnail_name}.jpg"

        # Create foldername
        subfolder = self.subfolder_name(self.last_recording_start)
        full_path = os.path.join(self.recordings_folder, subfolder)
        create_directory(full_path)

        thumbnail_path = os.path.join(full_path, thumbnail_name)
        thumbnail = self.create_thumbnail(
            thumbnail_path,
            self._camera.shared_frames.get_decoded_frame_rgb(shared_frame),
            objects_in_fov,
            resolution,
        )
        self._last_recording_path = os.path.join(full_path, video_name)
        self._last_recording_thumbnail_path = thumbnail_path

        self._start(shared_frame, objects_in_fov, resolution)
        self._vis.dispatch_event(
            EVENT_RECORDER_START.format(camera_identifier=self._camera.identifier),
            EventRecorderStart(
                start_time=self.last_recording_start,
                path=self.last_recording_path,
                thumbnail=thumbnail,
                thumbnail_path=thumbnail_path
                if self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_SAVE_TO_DISK]
                else None,
                objects=objects_in_fov,
            ),
        )

    @abstractmethod
    def _start(
        self,
        shared_frame: SharedFrame,
        objects_in_fov: list[DetectedObject],
        resolution,
    ):
        """Start the recorder."""

    def stop(self):
        """Stop recording."""
        self._logger.info("Stopping recorder")
        self._last_recording_end = datetime.datetime.now()
        self._stop()
        self._vis.dispatch_event(
            EVENT_RECORDER_STOP.format(camera_identifier=self._camera.identifier),
            EventRecorderStop(
                start_time=self.last_recording_start,
                end_time=self.last_recording_end,
                path=self.last_recording_path,
                thumbnail_path=self.last_recording_thumbnail_path
                if self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_SAVE_TO_DISK]
                else None,
            ),
        )
        self.is_recording = False

    @abstractmethod
    def _stop(
        self,
    ):
        """Stop the recorder."""

    @property
    def idle_timeout(self):
        """Return idle timeout."""
        return self._config[CONFIG_RECORDER][CONFIG_IDLE_TIMEOUT]

    @property
    def last_recording_path(self) -> str:
        """Return last recording path."""
        return self._last_recording_path

    @property
    def last_recording_start(self) -> datetime.datetime:
        """Return last recording start time."""
        return self._last_recording_start

    @property
    def last_recording_end(self) -> datetime.datetime:
        """Return last recording end time."""
        return self._last_recording_end

    @property
    def last_recording_thumbnail_path(self) -> str:
        """Return last recording thumbnail path."""
        return self._last_recording_thumbnail_path

    def cleanup_recordings(self):
        """Delete all recordings that have past the configured days to retain."""
        self._logger.debug("Running cleanup")
        retention_period = time.time() - (
            self._config[CONFIG_RECORDER][CONFIG_RETAIN] * 24 * 60 * 60
        )
        dirs = Path(self.recordings_folder)

        extensions = [
            f"*.{self._config[CONFIG_RECORDER][CONFIG_EXTENSION]}",
            "*.mp4",
            "*.mkv",
            "*.jpg",
        ]
        for extension in extensions:
            files = dirs.walkfiles(extension)
            for file in files:
                if file.mtime <= retention_period:
                    self._logger.debug(f"Removing file {file}")
                    file.remove()

        folders = dirs.walkdirs("*-*-*")
        for folder in folders:
            self._logger.debug(f"Items in {folder}: {len(folder.listdir())}")
            if len(folder.listdir()) == 0:
                try:
                    folder.rmdir()
                    self._logger.debug(f"Removing directory {folder}")
                except OSError:
                    self._logger.error(f"Could not remove directory {folder}")
