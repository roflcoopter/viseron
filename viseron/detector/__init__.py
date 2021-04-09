"""Interface to different object detectors."""
import importlib
import logging
from queue import Queue
from threading import Lock, Thread

import cv2
from voluptuous import Any, Optional, Required

from viseron.config.config_logging import LoggingConfig
from viseron.config.config_object_detection import SCHEMA as BASE_SCEHMA
from viseron.const import TOPIC_FRAME_PROCESSED_OBJECT, TOPIC_FRAME_SCAN_OBJECT
from viseron.data_stream import DataStream
from viseron.helpers import calculate_relative_coords

LOGGER = logging.getLogger(__name__)

SCHEMA = BASE_SCEHMA.extend(
    {
        Required("type"): str,
        Optional("model_width", default=None): Any(int, None),
        Optional("model_height", default=None): Any(int, None),
    }
)


class Detector:
    """Subscribe to frames and run object detection using the configured detector."""

    def __init__(self, object_detection_config):
        detector = importlib.import_module(
            "viseron.detector." + object_detection_config["type"]
        )
        config = detector.Config(detector.SCHEMA(object_detection_config))
        if getattr(config.logging, "level", None):
            LOGGER.setLevel(config.logging.level)

        LOGGER.debug(f"Initializing object detector {object_detection_config['type']}")

        self.config = config
        self.detection_lock = Lock()

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            LOGGER.debug("OpenCL activated")
            cv2.ocl.setUseOpenCL(True)

        self.object_detector = detector.ObjectDetection(config)

        self._topic_scan_object = f"*/{TOPIC_FRAME_SCAN_OBJECT}"
        self._object_detection_queue = Queue()
        object_detection_thread = Thread(target=self.object_detection)
        object_detection_thread.daemon = True
        object_detection_thread.start()
        DataStream.subscribe_data(self._topic_scan_object, self._object_detection_queue)

        LOGGER.debug("Object detector initialized")

    def object_detection(self):
        """Perform object detection and publish the results."""
        while True:
            frame = self._object_detection_queue.get()
            self.detection_lock.acquire()
            frame["frame"].objects = self.object_detector.return_objects(frame)
            self.detection_lock.release()
            DataStream.publish_data(
                (
                    f"{frame['camera_config'].camera.name_slug}/"
                    f"{TOPIC_FRAME_PROCESSED_OBJECT}"
                ),
                frame,
            )

    @property
    def model_width(self):
        """Return width of the object detection model."""
        return (
            self.config.model_width
            if self.config.model_width
            else self.object_detector.model_width
        )

    @property
    def model_height(self):
        """Return height of the object detection model."""
        return (
            self.config.model_height
            if self.config.model_height
            else self.object_detector.model_height
        )


class DetectorConfig:
    """Config object for a detector. All object detector configs must inherit
    from this class."""

    def __init__(self, object_detection):
        self._model_path = object_detection["model_path"]
        self._label_path = object_detection["label_path"]
        self._model_width = object_detection["model_width"]
        self._model_height = object_detection["model_height"]
        self._logging = None
        if object_detection.get("logging", None):
            self._logging = LoggingConfig(object_detection["logging"])

    @property
    def model_path(self):
        """Return path to object detection model."""
        return self._model_path

    @property
    def label_path(self):
        """Return path to object detection labels."""
        return self._label_path

    @property
    def model_width(self):
        """Return width of the object detection model."""
        return self._model_width

    @property
    def model_height(self):
        """Return height of the object detection model."""
        return self._model_height

    @property
    def logging(self):
        """Return log settings."""
        return self._logging
