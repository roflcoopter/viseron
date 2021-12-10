"""Face recognition module."""
import datetime
import os
from dataclasses import dataclass
from threading import Timer
from typing import Dict, Tuple
from uuid import uuid4

import cv2
import voluptuous as vol

from viseron.domains.post_processor import BASE_CONFIG_SCHEMA, AbstractPostProcessor
from viseron.helpers import create_directory

from .const import (
    CONFIG_CAMERAS,
    CONFIG_EXPIRE_AFTER,
    CONFIG_FACE_RECOGNITION_PATH,
    CONFIG_SAVE_UNKNOWN_FACES,
    CONFIG_UNKNOWN_FACES_PATH,
    DEFAULT_EXPIRE_AFTER,
    DEFAULT_FACE_RECOGNITION_PATH,
    DEFAULT_SAVE_UNKNOWN_FACES,
    DEFAULT_UNKNOWN_FACES_PATH,
)

BASE_CONFIG_SCHEMA = BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_FACE_RECOGNITION_PATH, default=DEFAULT_FACE_RECOGNITION_PATH
        ): str,
        vol.Optional(
            CONFIG_SAVE_UNKNOWN_FACES, default=DEFAULT_SAVE_UNKNOWN_FACES
        ): bool,
        vol.Optional(
            CONFIG_UNKNOWN_FACES_PATH, default=DEFAULT_UNKNOWN_FACES_PATH
        ): str,
        vol.Optional(CONFIG_EXPIRE_AFTER, default=DEFAULT_EXPIRE_AFTER): vol.All(
            vol.Any(vol.All(int, vol.Range(min=0)), vol.All(float, vol.Range(min=0.0))),
            vol.Coerce(float),
        ),
        vol.Required(CONFIG_CAMERAS): {str: None},
    }
)


@dataclass
class FaceDict:
    """Representation of a face."""

    name: str
    coordinates: Tuple[int, int, int, int]
    timer: Timer


class AbstractFaceRecognition(AbstractPostProcessor):
    """Abstract face recognition."""

    def __init__(self, vis, config, camera_identifier):
        super().__init__(vis, config, camera_identifier)
        self._faces: Dict[str, FaceDict] = {}
        if config[CONFIG_SAVE_UNKNOWN_FACES]:
            create_directory(config[CONFIG_UNKNOWN_FACES_PATH])

    def known_face_found(self, face: str, coordinates: Tuple[int, int, int, int]):
        """Adds/expires known faces."""
        # Cancel the expiry timer if face has already been detected
        if self._faces.get(face, None):
            self._faces[face].timer.cancel()

        # if self._mqtt_devices.get(face, None):
        # self._mqtt_devices[face].publish(True)

        # Adds a detected face and schedules an expiry timer
        self._faces[face] = FaceDict(
            face,
            coordinates,
            Timer(self._config[CONFIG_EXPIRE_AFTER], self.expire_face, [face]),
        )
        self._faces[face].timer.start()

    def unknown_face_found(self, frame):
        """Save unknown faces."""
        unique_id = f"{datetime.datetime.now().strftime('%H:%M:%S-')}{str(uuid4())}.jpg"
        file_name = os.path.join(self._config[CONFIG_UNKNOWN_FACES_PATH], unique_id)
        self._logger.debug(f"Unknown face found, saving to {file_name}")

        if not cv2.imwrite(file_name, frame):
            self._logger.error("Failed saving unknown face image to disk")

    def expire_face(self, face):
        """Expire no longer found face."""
        self._logger.debug(f"Expiring face {face}")
        # self._mqtt_devices[face].publish(False)
        del self._faces[face]
