"""Recorder."""
import logging
import os
from threading import Thread

from viseron.domains.camera import CONFIG_LOOKBACK
from viseron.domains.camera.recorder import AbstractRecorder
from viseron.helpers import create_directory

from .const import COMPONENT, CONFIG_SEGMENTS_FOLDER, RECORDER
from .segments import SegmentCleanup, Segments

LOGGER = logging.getLogger(__name__)


class Recorder(AbstractRecorder):
    """Creates thumbnails and recordings."""

    def __init__(self, vis, config, camera):
        super().__init__(vis, COMPONENT, config, camera)
        self._logger.debug("Initializing ffmpeg recorder")
        self._recorder_config = config[RECORDER]

        self._event_start = None
        self._event_end = None

        segments_folder = os.path.join(
            self._recorder_config[CONFIG_SEGMENTS_FOLDER], self._camera.identifier
        )
        create_directory(segments_folder)
        self._segmenter = Segments(self._logger, config, segments_folder)
        self._segment_cleanup = SegmentCleanup(
            vis, self._recorder_config, self._camera.identifier, self._logger
        )

    def concat_segments(self):
        """Concatenate FFmpeg segments to a single video."""
        self._segmenter.concat_segments(
            self._event_start - self._recorder_config[CONFIG_LOOKBACK],
            self._event_end,
            self.last_recording_path,
        )
        # Dont resume cleanup if new recording started during encoding
        if not self.is_recording:
            self._segment_cleanup.resume()

    def _start(self, shared_frame, objects_in_fov, resolution):
        self._segment_cleanup.pause()
        self._event_start = int(self.last_recording_start.timestamp())

    def _stop(self):
        self._event_end = int(self.last_recording_end.timestamp())
        concat_thread = Thread(target=self.concat_segments)
        concat_thread.start()
