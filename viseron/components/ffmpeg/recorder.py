"""Recorder."""
import datetime
import logging
import os
from threading import Thread

import cv2

from viseron import helpers
from viseron.domains.camera import (
    CONFIG_EXTENSION,
    CONFIG_FILENAME_PATTERN,
    CONFIG_FOLDER,
    CONFIG_LOOKBACK,
    CONFIG_SAVE_TO_DISK,
    CONFIG_THUMBNAIL,
)

from .const import COMPONENT, CONFIG_SEGMENTS_FOLDER, RECORDER
from .segments import SegmentCleanup, Segments

LOGGER = logging.getLogger(__name__)


class Recorder:
    """Creates thumbnails and recordings."""

    def __init__(self, vis, config, camera_identifier):
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.debug("Initializing ffmpeg recorder")
        self._config = config
        self._recorder_config = self._config[RECORDER]
        self._camera_identifier = camera_identifier
        self._camera = vis.data[COMPONENT][camera_identifier]

        self.is_recording = False
        self.last_recording_start = None
        self.last_recording_end = None
        self._event_start = None
        self._event_end = None
        self._recording_name = None

        segments_folder = os.path.join(
            self._recorder_config[CONFIG_SEGMENTS_FOLDER], self._camera.identifier
        )
        self.create_directory(segments_folder)
        self._segmenter = Segments(self._logger, config, segments_folder)
        self._segment_cleanup = SegmentCleanup(
            self._recorder_config, self._camera.identifier, self._logger
        )

    def subfolder_name(self, today):
        """Generate name of folder for recording."""
        return f"{today.year:04}-{today.month:02}-{today.day:02}/{self._camera.name}"

    def create_thumbnail(self, file_name, frame, objects, resolution):
        """Create thumbnails, sent to MQTT and/or saved to disk based on config."""
        helpers.draw_objects(
            frame.decoded_frame_umat_rgb,
            objects,
            resolution,
        )
        cv2.imwrite(file_name, frame.decoded_frame_umat_rgb)

        if self._recorder_config[CONFIG_THUMBNAIL][CONFIG_SAVE_TO_DISK]:
            thumbnail_folder = os.path.join(
                self._recorder_config[CONFIG_FOLDER], "thumbnails", self._camera.name
            )
            self.create_directory(thumbnail_folder)

            self._logger.debug(f"Saving thumbnail in {thumbnail_folder}")
            if not cv2.imwrite(
                os.path.join(thumbnail_folder, "latest_thumbnail.jpg"),
                frame.decoded_frame_umat_rgb,
            ):
                self._logger.error("Failed saving thumbnail to disk")

    def create_directory(self, path):
        """Create a directory."""
        try:
            if not os.path.isdir(path):
                self._logger.debug(f"Creating folder {path}")
                os.makedirs(path)
        except FileExistsError:
            pass

    def start_recording(self, frame, objects, resolution):
        """Start recording."""
        self._logger.info("Starting recorder")
        self.is_recording = True
        self._segment_cleanup.pause()
        now = datetime.datetime.now()
        self.last_recording_start = now.isoformat()
        self.last_recording_end = None
        self._event_start = int(now.timestamp())

        if self._recorder_config[CONFIG_FOLDER] is None:
            self._logger.error("Output directory is not specified")
            return

        # Create filename
        now = datetime.datetime.now()
        video_name = (
            f"{now.strftime(self._recorder_config[CONFIG_FILENAME_PATTERN])}"
            f".{self._recorder_config[CONFIG_EXTENSION]}"
        )
        thumbnail_name = self._recorder_config[CONFIG_THUMBNAIL][
            CONFIG_FILENAME_PATTERN
        ]
        thumbnail_name = f"{thumbnail_name}.jpg"
        # Create foldername
        subfolder = self.subfolder_name(now)
        full_path = os.path.join(self._recorder_config[CONFIG_FOLDER], subfolder)
        self.create_directory(full_path)

        if frame:
            self.create_thumbnail(
                os.path.join(full_path, thumbnail_name), frame, objects, resolution
            )

        self._recording_name = os.path.join(full_path, video_name)

    def concat_segments(self):
        """Concatenate FFmpeg segments to a single video."""
        self._segmenter.concat_segments(
            self._event_start - self._recorder_config[CONFIG_LOOKBACK],
            self._event_end,
            self._recording_name,
        )
        # Dont resume cleanup if new recording started during encoding
        if not self.is_recording:
            self._segment_cleanup.resume()

    def stop_recording(self):
        """Stop recording."""
        self._logger.info("Stopping recorder")
        self.is_recording = False
        now = datetime.datetime.now()
        self.last_recording_end = now.isoformat()
        self._event_end = int(now.timestamp())
        concat_thread = Thread(target=self.concat_segments)
        concat_thread.start()
