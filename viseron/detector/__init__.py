"""Interface to different object detectors."""
import importlib
import logging
from abc import ABC, abstractmethod
from queue import Queue
from threading import Lock

import cv2
from voluptuous import PREVENT_EXTRA

from viseron.camera.frame_decoder import FrameToScan
from viseron.config.config_object_detection import ObjectDetectionConfig
from viseron.const import TOPIC_FRAME_PROCESSED_OBJECT, TOPIC_FRAME_SCAN_OBJECT
from viseron.data_stream import DataStream
from viseron.exceptions import (
    DetectorConfigError,
    DetectorConfigSchemaError,
    DetectorImportError,
)
from viseron.thread_watchdog import RestartableThread

LOGGER = logging.getLogger(__name__)


class AbstractObjectDetection(ABC):
    """Abstract Object Detection."""

    def preprocess(self, frame_to_scan: FrameToScan):  # pylint: disable=no-self-use
        """Optional preprocessor function that runs before detection."""
        return frame_to_scan

    @abstractmethod
    def return_objects(self, frame_to_scan: FrameToScan):
        """Perform object detection."""


class AbstractDetectorConfig(ABC, ObjectDetectionConfig):
    """Abstract Object Detector Config."""

    SCHEMA = ObjectDetectionConfig.schema.extend({}, extra=PREVENT_EXTRA)


class Detector:
    """Subscribe to frames and run object detection using the configured detector."""

    def __init__(self, object_detection_config):
        detector_module = importlib.import_module(
            "viseron.detector." + object_detection_config["type"]
        )
        if hasattr(detector_module, "ObjectDetection") and issubclass(
            detector_module.ObjectDetection, AbstractObjectDetection
        ):
            pass
        else:
            raise DetectorImportError(object_detection_config["type"])

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

        config = config_module.Config(config_module.SCHEMA(object_detection_config))
        if getattr(config.logging, "level", None):
            LOGGER.setLevel(config.logging.level)

        LOGGER.debug(f"Initializing object detector {config.type}")

        self.detection_lock = Lock()

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            LOGGER.debug("OpenCL activated")
            cv2.ocl.setUseOpenCL(True)

        self.object_detector = detector_module.ObjectDetection(config)

        self._topic_scan_object = f"*/{TOPIC_FRAME_SCAN_OBJECT}"
        self._object_detection_queue: Queue[  # pylint: disable=unsubscriptable-object
            FrameToScan
        ] = Queue()
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
            with self.detection_lock:
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
