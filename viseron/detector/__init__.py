"""Interface to different object detectors."""
from __future__ import annotations

import importlib
import logging
import time
from abc import ABC, abstractmethod
from queue import Queue
from threading import Lock
from typing import TYPE_CHECKING

import cv2
from voluptuous import PREVENT_EXTRA

from viseron.components.data_stream import DataStream
from viseron.config.config_object_detection import ObjectDetectionConfig
from viseron.const import TOPIC_FRAME_PROCESSED_OBJECT, TOPIC_FRAME_SCAN_OBJECT
from viseron.exceptions import (
    DetectorConfigError,
    DetectorConfigSchemaError,
    DetectorImportError,
    DetectorModuleNotFoundError,
)
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron.camera.frame_decoder import FrameToScan

LOGGER = logging.getLogger(__name__)


class AbstractObjectDetection(ABC):
    """Abstract Object Detection."""

    def preprocess(self, frame_to_scan: FrameToScan):  # pylint: disable=no-self-use
        """Preprocessor function that runs before detection."""
        return frame_to_scan

    @abstractmethod
    def return_objects(self, frame_to_scan: FrameToScan):
        """Perform object detection."""


class AbstractDetectorConfig(ABC, ObjectDetectionConfig):
    """Abstract Object Detector Config."""

    SCHEMA = ObjectDetectionConfig.schema.extend({}, extra=PREVENT_EXTRA)


class Detector:
    """Subscribe to frames and run object detection using the configured detector."""

    lock = Lock()

    def __init__(self, object_detection_config):
        # Config is not validated yet so we need to access the dictionary value
        if not object_detection_config["enable"]:
            return

        config_module, detector_module = import_object_detection(
            object_detection_config
        )

        config = config_module.Config(config_module.SCHEMA(object_detection_config))
        LOGGER.debug(f"Initializing object detector {config.type}")

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            LOGGER.debug("OpenCL activated")
            cv2.ocl.setUseOpenCL(True)

        self.object_detector = detector_module.ObjectDetection(config)

        self._topic_scan_object = f"*/{TOPIC_FRAME_SCAN_OBJECT}"
        self._object_detection_queue: Queue[  # pylint: disable=unsubscriptable-object
            FrameToScan
        ] = Queue(maxsize=100)
        object_detection_thread = RestartableThread(
            target=self.object_detection,
            name="object_detection",
            register=True,
            daemon=True,
        )
        object_detection_thread.daemon = True
        object_detection_thread.start()
        DataStream.subscribe_data(self._topic_scan_object, self._object_detection_queue)

        LOGGER.debug("Object detector initialized")

    def object_detection(self):
        """Perform object detection and publish the results."""
        while True:
            frame_to_scan: FrameToScan = self._object_detection_queue.get()
            if (
                frame_age := time.time() - frame_to_scan.capture_time
            ) > frame_to_scan.camera_config.object_detection.max_frame_age:
                LOGGER.debug(
                    f"Frame is {frame_age} seconds old for "
                    f"{frame_to_scan.decoder_name}. Discarding"
                )
                continue

            frame_to_scan.frame.objects = self.object_detector.return_objects(
                frame_to_scan
            )
            DataStream.publish_data(
                (
                    f"{frame_to_scan.camera_config.camera.name_slug}/"
                    f"{TOPIC_FRAME_PROCESSED_OBJECT}"
                ),
                frame_to_scan,
            )


def import_object_detection(object_detection_config):
    """Dynamically import object detector."""
    try:
        detector_module = importlib.import_module(
            "viseron.detector." + object_detection_config["type"]
        )
        if hasattr(detector_module, "ObjectDetection") and issubclass(
            detector_module.ObjectDetection, AbstractObjectDetection
        ):
            pass
        else:
            raise DetectorImportError(object_detection_config["type"])
    except ModuleNotFoundError as error:
        raise DetectorModuleNotFoundError(object_detection_config["type"]) from error

    detector_config_module = None
    try:
        detector_config_module = importlib.import_module(
            "viseron.detector." + object_detection_config["type"] + ".config"
        )
    except ModuleNotFoundError:
        pass

    config_module = (
        detector_config_module if detector_config_module else detector_module
    )
    if hasattr(config_module, "Config") and issubclass(
        config_module.Config, AbstractDetectorConfig
    ):
        pass
    else:
        raise DetectorConfigError(object_detection_config["type"])

    if not hasattr(config_module, "SCHEMA"):
        raise DetectorConfigSchemaError(object_detection_config["type"])

    return config_module, detector_module
