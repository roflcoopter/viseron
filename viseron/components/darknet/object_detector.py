"""Darknet object detector."""

from __future__ import annotations

import logging
import os
import threading
from queue import Queue
from typing import TYPE_CHECKING, Any

from viseron.const import ENV_CUDA_SUPPORTED
from viseron.domains.object_detector import AbstractObjectDetector
from viseron.domains.object_detector.const import DOMAIN
from viseron.exceptions import DomainNotReady

from . import DarknetDNN, DarknetNative, LoadDarknetError
from .const import (
    COMPONENT,
    CONFIG_DNN_BACKEND,
    CONFIG_DNN_TARGET,
    CONFIG_OBJECT_DETECTOR,
)

if TYPE_CHECKING:
    import numpy as np

    from viseron import Viseron
    from viseron.domains.camera.shared_frames import SharedFrame
    from viseron.domains.object_detector.detected_object import DetectedObject


LOGGER = logging.getLogger(__name__)

SETUP_LOCK = threading.Lock()


def setup(vis: Viseron, config: dict[str, Any], identifier: str) -> bool:
    """Set up the darknet object_detector domain."""
    with SETUP_LOCK:
        if not vis.data[COMPONENT].get(CONFIG_OBJECT_DETECTOR, None):
            if (
                os.getenv(ENV_CUDA_SUPPORTED) == "true"
                and config[CONFIG_OBJECT_DETECTOR][CONFIG_DNN_BACKEND] is None
                and config[CONFIG_OBJECT_DETECTOR][CONFIG_DNN_TARGET] is None
            ):
                try:
                    vis.data[COMPONENT][CONFIG_OBJECT_DETECTOR] = DarknetNative(
                        vis, config[CONFIG_OBJECT_DETECTOR]
                    )
                except LoadDarknetError as error:
                    raise DomainNotReady from error
            else:
                vis.data[COMPONENT][CONFIG_OBJECT_DETECTOR] = DarknetDNN(
                    vis, config[CONFIG_OBJECT_DETECTOR]
                )
        else:
            LOGGER.debug("Darknet detector has already been created")

    ObjectDetector(vis, config[DOMAIN], identifier)

    return True


def unload(vis: Viseron) -> None:
    """Unload the darknet object_detector domain."""
    if detector := vis.data.get(COMPONENT, {}).get(CONFIG_OBJECT_DETECTOR, None):
        detector.stop()
        vis.data[COMPONENT].pop(CONFIG_OBJECT_DETECTOR, None)


class ObjectDetector(AbstractObjectDetector):
    """Performs object detection."""

    def __init__(
        self, vis: Viseron, config: dict[str, Any], camera_identifier: str
    ) -> None:
        self._darknet = vis.data[COMPONENT][CONFIG_OBJECT_DETECTOR]
        self._object_result_queue: Queue[list[DetectedObject]] = Queue(maxsize=1)
        super().__init__(vis, COMPONENT, config, camera_identifier)

    def preprocess(self, frame: np.ndarray) -> np.ndarray | bytes:
        """Return preprocessed frame before performing object detection."""
        return self._darknet.preprocess(frame)

    def return_objects(self, frame: SharedFrame) -> list[DetectedObject] | None:
        """Perform object detection."""
        detections = self._darknet.detect(
            frame,
            self._camera_identifier,
            self._object_result_queue,
            self.min_confidence,
        )
        if detections is None:
            return None
        return self._darknet.post_process(detections, self._camera.resolution)

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._darknet.model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._darknet.model_height

    @property
    def model_res(self) -> tuple[int, int]:
        """Return trained model resolution."""
        return self._darknet.model_res
