"""Recorder."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from viseron.domains.camera.recorder import AbstractRecorder

from .const import COMPONENT, RECORDER

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


class Recorder(AbstractRecorder):
    """Creates thumbnails and recordings."""

    def __init__(self, vis: Viseron, config, camera: AbstractCamera) -> None:
        super().__init__(vis, COMPONENT, config, camera)
        self._logger.debug("Initializing recorder")
        self._recorder_config = config[RECORDER]

    def _start(self, recording, shared_frame, objects_in_fov) -> None:
        pass

    def _stop(self, recording) -> None:
        pass
