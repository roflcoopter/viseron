"""Recorder."""
from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING

from viseron.components.ffmpeg.recorder import ConcatThreadsContext
from viseron.domains.camera.recorder import AbstractRecorder
from viseron.helpers import create_directory

from .const import COMPONENT, CONFIG_SEGMENTS_FOLDER, RECORDER
from .segments import SegmentCleanup, Segments

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.camera.recorder import Recording
LOGGER = logging.getLogger(__name__)


class Recorder(AbstractRecorder):
    """Creates thumbnails and recordings."""

    def __init__(self, vis: Viseron, config, camera: AbstractCamera):
        super().__init__(vis, COMPONENT, config, camera)
        self._logger.debug("Initializing gstreamer recorder")
        self._recorder_config = config[RECORDER]

        self._segment_thread_context = ConcatThreadsContext()
        self._concat_thread_lock = threading.Lock()

        segments_folder = os.path.join(
            self._recorder_config[CONFIG_SEGMENTS_FOLDER], self._camera.identifier
        )
        create_directory(segments_folder)
        self._segmenter = Segments(self._logger, config, vis, camera, segments_folder)
        self._segment_cleanup = SegmentCleanup(
            vis,
            self._recorder_config,
            self._camera.identifier,
            self._logger,
            self._segment_thread_context,
        )

    def concat_segments(self, recording: Recording):
        """Concatenate GStreamer segments to a single video."""
        with self._segment_thread_context:
            with self._concat_thread_lock:
                self._segment_cleanup.pause()
                self._segmenter.concat_segments(recording)

                # Dont resume cleanup if new recording started during encoding
                if not self.is_recording:
                    self._segment_cleanup.resume()

    def _start(self, recording, shared_frame, objects_in_fov, resolution):
        self._segment_cleanup.pause()

    def _stop(self, recording):
        concat_thread = threading.Thread(target=self.concat_segments, args=(recording,))
        concat_thread.start()
