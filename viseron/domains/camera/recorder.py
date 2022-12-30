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
class EventRecorderData:
    """Hold information on recorder start/stop/complete event."""

    camera: AbstractCamera
    recording: Recording

    def as_dict(self):
        """Return as dict."""
        return {
            "camera": self.camera,
            "recording": self.recording,
        }


@dataclass
class Recording:
    """Recording dict representation."""

    start_time: datetime.datetime
    start_timestamp: float
    end_time: datetime.datetime | None
    end_timestamp: float | None
    date: str
    path: str
    filename: str
    thumbnail: np.ndarray | None
    thumbnail_path: str | None
    objects: list[DetectedObject]

    def as_dict(self):
        """Return as dict."""
        return {
            "start_time": self.start_time,
            "start_timestamp": self.start_timestamp,
            "end_time": self.end_time,
            "end_timestamp": self.end_timestamp,
            "date": self.date,
            "path": self.path,
            "filename": self.filename,
            "thumbnail_path": self.thumbnail_path,
            "objects": self.objects,
        }


class AbstractRecorder(ABC):
    """Abstract recorder."""

    def __init__(self, vis, component, config, camera):
        self._logger = logging.getLogger(self.__module__ + "." + camera.identifier)
        self._vis = vis
        self._config = config
        self._camera: AbstractCamera = camera

        self.is_recording = False
        self._active_recording: Recording | None = None
        self._extensions = list(
            {
                f"*.{self._camera.extension}",
                "*.mp4",
                "*.mkv",
                "*.mov",
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
        start_time = datetime.datetime.now()

        if self._config[CONFIG_RECORDER][CONFIG_FOLDER] is None:
            self._logger.error("Output directory is not specified")
            return

        # Create filename
        filename_pattern = start_time.strftime(
            self._config[CONFIG_RECORDER][CONFIG_FILENAME_PATTERN]
        )
        video_name = f"{filename_pattern}.{self._camera.extension}"
        thumbnail_name = start_time.strftime(
            self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_FILENAME_PATTERN]
        )
        thumbnail_name = f"{thumbnail_name}.jpg"

        # Create foldername
        subfolder = self.subfolder_name(start_time)
        full_path = os.path.join(self.recordings_folder, subfolder)
        create_directory(full_path)

        thumbnail_path = os.path.join(full_path, thumbnail_name)
        thumbnail = self.create_thumbnail(
            thumbnail_path,
            self._camera.shared_frames.get_decoded_frame_rgb(shared_frame),
            objects_in_fov,
            resolution,
        )

        start_time = datetime.datetime.now()

        recording = Recording(
            start_time=start_time,
            start_timestamp=start_time.timestamp(),
            end_time=None,
            end_timestamp=None,
            date=subfolder,
            path=os.path.join(full_path, video_name),
            filename=video_name,
            thumbnail=thumbnail,
            thumbnail_path=thumbnail_path
            if self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_SAVE_TO_DISK]
            else None,
            objects=objects_in_fov,
        )

        self._start(recording, shared_frame, objects_in_fov, resolution)
        self._active_recording = recording
        self._vis.dispatch_event(
            EVENT_RECORDER_START.format(camera_identifier=self._camera.identifier),
            EventRecorderData(
                camera=self._camera,
                recording=recording,
            ),
        )
        return recording

    @abstractmethod
    def _start(
        self,
        recording: Recording,
        shared_frame: SharedFrame,
        objects_in_fov: list[DetectedObject],
        resolution,
    ):
        """Start the recorder."""

    def stop(self, recording: Recording):
        """Stop recording."""
        self._logger.info("Stopping recorder")
        end_time = datetime.datetime.now()
        recording.end_time = end_time
        recording.end_timestamp = end_time.timestamp()
        self._stop(recording)
        self._active_recording = None
        self._vis.dispatch_event(
            EVENT_RECORDER_STOP.format(camera_identifier=self._camera.identifier),
            EventRecorderData(
                camera=self._camera,
                recording=recording,
            ),
        )
        self.is_recording = False

    @abstractmethod
    def _stop(self, recording: Recording):
        """Stop the recorder."""

    @property
    def idle_timeout(self):
        """Return idle timeout."""
        return self._config[CONFIG_RECORDER][CONFIG_IDLE_TIMEOUT]

    @property
    def active_recording(self) -> Recording | None:
        """Return active recording."""
        return self._active_recording

    def cleanup_recordings(self):
        """Delete all recordings that have past the configured days to retain."""
        self._logger.debug("Running cleanup")
        retention_period = time.time() - (
            self._config[CONFIG_RECORDER][CONFIG_RETAIN] * 24 * 60 * 60
        )
        dirs = Path(self.recordings_folder)

        extensions = [
            f"*.{self._camera.extension}",
            "*.mov",
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
