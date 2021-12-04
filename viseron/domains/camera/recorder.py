"""Base recorder."""
from __future__ import annotations

import datetime
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

import cv2
import numpy as np

from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.helpers import draw_objects

from .const import (
    CONFIG_EXTENSION,
    CONFIG_FILENAME_PATTERN,
    CONFIG_FOLDER,
    CONFIG_IDLE_TIMEOUT,
    CONFIG_RECORDER,
    CONFIG_SAVE_TO_DISK,
    CONFIG_THUMBNAIL,
)
from .shared_frames import SharedFrame

if TYPE_CHECKING:
    from . import AbstractCamera


EVENT_RECORDER_START = "{camera_identifier}/recorder/start"
EVENT_RECORDER_STOP = "{camera_identifier}/recorder/stop"


@dataclass
class EventRecorderStart:
    """Hold information on recorder start event."""

    start_time: datetime.datetime
    thumbnail: np.ndarray
    objects: List[DetectedObject]


@dataclass
class EventRecorderStop:
    """Hold information on recorder stop event."""

    start_time: datetime.datetime
    end_time: datetime.datetime
    filename: os.PathLike


class AbstractRecorder(ABC):
    """Abstract recorder."""

    def __init__(self, vis, config, camera):
        self._logger = logging.getLogger(self.__module__ + "." + camera.identifier)
        self._vis = vis
        self._config = config
        self._camera: AbstractCamera = camera

        self.is_recording = False
        self._last_recording_path = None
        self._last_recording_start = None
        self._last_recording_end = None

    def subfolder_name(self, today):
        """Generate name of folder for recording."""
        return f"{today.year:04}-{today.month:02}-{today.day:02}/{self._camera.name}"

    def create_directory(self, path):
        """Create a directory."""
        try:
            if not os.path.isdir(path):
                self._logger.debug(f"Creating folder {path}")
                os.makedirs(path)
        except FileExistsError:
            pass

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
            self.create_directory(thumbnail_folder)

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
        objects_in_fov: List[DetectedObject],
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
            f"{filename_pattern}" f".{self._config[CONFIG_RECORDER][CONFIG_EXTENSION]}"
        )
        thumbnail_name = self.last_recording_start.strftime(
            self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_FILENAME_PATTERN]
        )
        thumbnail_name = f"{thumbnail_name}.jpg"
        # Create foldername
        subfolder = self.subfolder_name(self.last_recording_start)
        full_path = os.path.join(
            self._config[CONFIG_RECORDER][CONFIG_FOLDER], subfolder
        )
        self.create_directory(full_path)

        thumbnail = self.create_thumbnail(
            os.path.join(full_path, thumbnail_name),
            self._camera.shared_frames.get_decoded_frame_rgb(shared_frame),
            objects_in_fov,
            resolution,
        )
        self._last_recording_path = os.path.join(full_path, video_name)

        self._start(shared_frame, objects_in_fov, resolution)
        self._vis.dispatch_event(
            EVENT_RECORDER_START.format(camera_identifier=self._camera.identifier),
            EventRecorderStart(
                start_time=self.last_recording_start,
                thumbnail=thumbnail,
                objects=objects_in_fov,
            ),
        )

    @abstractmethod
    def _start(
        self,
        shared_frame: SharedFrame,
        objects_in_fov: List[DetectedObject],
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
                end_time=self.last_recording_start,
                filename=self.last_recording_path,
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
    def last_recording_path(self) -> os.PathLike:
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
