"""Recorder."""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from viseron.domains.camera.recorder import AbstractRecorder

from .const import COMPONENT, RECORDER
from .segments import Segments

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.camera.recorder import Recording

LOGGER = logging.getLogger(__name__)


class Recorder(AbstractRecorder):
    """Creates thumbnails and recordings."""

    def __init__(self, vis: Viseron, config, camera: AbstractCamera) -> None:
        super().__init__(vis, COMPONENT, config, camera)
        self._logger.debug("Initializing recorder")
        self._recorder_config = config[RECORDER]
        self._concat_thread_lock = threading.Lock()
        self._segmenter = Segments(
            self._logger, config, vis, camera, self.segments_folder
        )

    def concat_segments(self, recording: Recording) -> None:
        """Concatenate FFmpeg segments to a single video."""
        with self._concat_thread_lock:
            self._segmenter.concat_segments(recording)

    def _start(self, recording, shared_frame, objects_in_fov, resolution) -> None:
        pass

    def _stop(self, recording) -> None:
        concat_thread = threading.Thread(target=self.concat_segments, args=(recording,))
        concat_thread.start()
