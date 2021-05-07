"""Face recognition module."""
import datetime
import logging
import os
from abc import abstractmethod
from dataclasses import dataclass
from queue import Queue
from threading import Timer
from typing import Any as TypeAny, Dict, Tuple
from uuid import uuid4

import cv2
from voluptuous import All, Any, Coerce, Optional, Range

from viseron.config import ViseronConfig
from viseron.helpers import create_directory, slugify
from viseron.mqtt.binary_sensor import MQTTBinarySensor
from viseron.post_processors import (
    AbstractProcessor,
    AbstractProcessorConfig,
    PostProcessorFrame,
)
from viseron.post_processors.face_recognition.defaults import (
    EXPIRE_AFTER,
    FACE_RECOGNITION_PATH,
    SAVE_UNKNOWN_FACES,
    UNKNOWN_FACES_PATH,
)

SCHEMA = AbstractProcessorConfig.SCHEMA.extend(
    {
        Optional("face_recognition_path", default=FACE_RECOGNITION_PATH): str,
        Optional("save_unknown_faces", default=SAVE_UNKNOWN_FACES): bool,
        Optional("unknown_faces_path", default=UNKNOWN_FACES_PATH): str,
        Optional("expire_after", default=EXPIRE_AFTER): All(
            Any(All(int, Range(min=0)), All(float, Range(min=0.0))), Coerce(float)
        ),
    }
)


@dataclass
class FaceDict:
    """Representation of a face."""

    name: str
    coordinates: Tuple[int, int, int, int]
    timer: Timer


class AbstractFaceRecognitionConfig(AbstractProcessorConfig):
    """Abstract face recognition config."""

    SCHEMA = SCHEMA

    def __init__(
        self,
        processor_config: Dict[str, TypeAny],
    ):
        super().__init__(processor_config)
        self._face_recognition_path = processor_config["face_recognition_path"]
        self._save_unknown_faces = processor_config["save_unknown_faces"]
        self._unknown_faces_path = processor_config["unknown_faces_path"]
        self._expire_after = processor_config["expire_after"]

    @property
    def face_recognition_path(self):
        """Return path to folders with faces."""
        return self._face_recognition_path

    @property
    def save_unknown_faces(self):
        """Return if unknown faces should be saved."""
        return self._save_unknown_faces

    @property
    def unknown_faces_path(self):
        """Return path to folder where unknown faces are saved."""
        return self._unknown_faces_path

    @property
    def expire_after(self):
        """Return number of seconds after a face is no longer detected to expire it."""
        return self._expire_after


class AbstractFaceRecognition(AbstractProcessor):
    """Abstract face recognition."""

    def __init__(
        self,
        config: ViseronConfig,
        processor_config: AbstractFaceRecognitionConfig,
        mqtt_queue: Queue,
        logger: logging.Logger,
    ):
        super().__init__(config, processor_config, mqtt_queue, logger)
        self._faces: Dict[str, FaceDict] = {}
        self._mqtt_devices: Dict[str, FaceMQTTBinarySensor] = {}
        self._processor_config = processor_config
        self._logger = logger
        if processor_config.save_unknown_faces:
            create_directory(processor_config.unknown_faces_path)

    def known_face_found(self, face: str, coordinates: Tuple[int, int, int, int]):
        """Adds/expires known faces."""
        # Cancel the expiry timer if face has already been detected
        if self._faces.get(face, None):
            self._faces[face].timer.cancel()

        if self._mqtt_devices.get(face, None):
            self._mqtt_devices[face].publish(True)

        # Adds a detected face and schedules an expiry timer
        self._faces[face] = FaceDict(
            face,
            coordinates,
            Timer(self._processor_config.expire_after, self.expire_face, [face]),
        )
        self._faces[face].timer.start()

    def unknown_face_found(self, frame):
        """Saves unknown faces."""
        unique_id = f"{datetime.datetime.now().strftime('%H:%M:%S-')}{str(uuid4())}.jpg"
        file_name = os.path.join(self._processor_config.unknown_faces_path, unique_id)
        self._logger.debug(f"Unknown face found, saving to {file_name}")

        if not cv2.imwrite(file_name, frame):
            self._logger.error("Failed saving unknown face image to disk")

    @abstractmethod
    def process(self, frame_to_process: PostProcessorFrame):
        """Perform face recognition."""

    def expire_face(self, face):
        """Expire no longer found face."""
        self._logger.debug(f"Expiring face {face}")
        self._mqtt_devices[face].publish(False)
        del self._faces[face]

    def on_connect(self, client):
        """Called when MQTT connection is established."""
        for device in self._mqtt_devices.values():
            device.on_connect(client)


class FaceMQTTBinarySensor(MQTTBinarySensor):
    """MQTT binary sensor representing a face."""

    # pylint: disable=super-init-not-called
    def __init__(self, config, mqtt_queue, face):
        self._config = config
        self._mqtt_queue = mqtt_queue
        self._name = f"{config.mqtt.client_id} Face detected {face}"
        self._friendly_name = f"Face detected {face}"
        self._device_name = config.mqtt.client_id
        self._unique_id = self._name
        self._node_id = slugify(config.mqtt.client_id)
        self._object_id = f"face_detected_{slugify(face)}"

    @property
    def state_topic(self):
        """Return state topic."""
        return f"{self._config.mqtt.client_id}/binary_sensor/{self.object_id}/state"
