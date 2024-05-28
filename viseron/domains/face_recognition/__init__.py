"""Face recognition module."""
from __future__ import annotations

import os
from abc import abstractmethod
from dataclasses import dataclass
from threading import Timer
from typing import Any

import voluptuous as vol
from sqlalchemy import insert

from viseron.components.storage.models import PostProcessorResults
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.domains.post_processor import (
    BASE_CONFIG_SCHEMA,
    AbstractPostProcessor,
    PostProcessorFrame,
)
from viseron.events import EventData
from viseron.helpers import calculate_relative_coords
from viseron.helpers.schemas import FLOAT_MIN_ZERO
from viseron.helpers.validators import Deprecated

from .binary_sensor import FaceDetectionBinarySensor
from .const import (
    CONFIG_EXPIRE_AFTER,
    CONFIG_FACE_RECOGNITION_PATH,
    CONFIG_SAVE_FACES,
    CONFIG_SAVE_UNKNOWN_FACES,
    CONFIG_UNKNOWN_FACES_PATH,
    DEFAULT_EXPIRE_AFTER,
    DEFAULT_FACE_RECOGNITION_PATH,
    DEFAULT_SAVE_FACES,
    DEFAULT_SAVE_UNKNOWN_FACES,
    DESC_EXPIRE_AFTER,
    DESC_FACE_RECOGNITION_PATH,
    DESC_SAVE_FACES,
    DESC_SAVE_UNKNOWN_FACES,
    DESC_UNKNOWN_FACES_PATH,
    DOMAIN,
    EVENT_FACE_DETECTED,
    EVENT_FACE_EXPIRED,
    UNKNOWN_FACE,
)

BASE_CONFIG_SCHEMA = BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_FACE_RECOGNITION_PATH,
            default=DEFAULT_FACE_RECOGNITION_PATH,
            description=DESC_FACE_RECOGNITION_PATH,
        ): str,
        vol.Optional(
            CONFIG_SAVE_UNKNOWN_FACES,
            default=DEFAULT_SAVE_UNKNOWN_FACES,
            description=DESC_SAVE_UNKNOWN_FACES,
        ): bool,
        Deprecated(
            CONFIG_UNKNOWN_FACES_PATH,
            description=DESC_UNKNOWN_FACES_PATH,
        ): str,
        vol.Optional(
            CONFIG_EXPIRE_AFTER,
            default=DEFAULT_EXPIRE_AFTER,
            description=DESC_EXPIRE_AFTER,
        ): FLOAT_MIN_ZERO,
        vol.Optional(
            CONFIG_SAVE_FACES,
            default=DEFAULT_SAVE_FACES,
            description=DESC_SAVE_FACES,
        ): bool,
    }
)


@dataclass
class FaceDict:
    """Representation of a face."""

    name: str
    coordinates: tuple[int, int, int, int]
    confidence: float | None
    timer: Timer
    extra_attributes: None | dict[str, Any] = None

    def as_dict(self) -> dict[str, Any]:
        """Return as dict."""
        return {
            "name": self.name,
            "coordinates": self.coordinates,
            "confidence": self.confidence,
            "extra_attributes": self.extra_attributes,
        }


@dataclass
class EventFaceDetected(EventData):
    """Hold information on face detection event."""

    camera_identifier: str
    face: FaceDict

    def as_dict(self) -> dict[str, Any]:
        """Return as dict."""
        return {
            "camera_identifier": self.camera_identifier,
            "face": self.face.as_dict(),
        }


class AbstractFaceRecognition(AbstractPostProcessor):
    """Abstract face recognition."""

    def __init__(self, vis, component, config, camera_identifier) -> None:
        super().__init__(vis, config, camera_identifier)
        self._faces: dict[str, FaceDict] = {}

        for face_dir in os.listdir(config[CONFIG_FACE_RECOGNITION_PATH]):
            if face_dir == "unknown":
                continue
            vis.add_entity(
                component, FaceDetectionBinarySensor(vis, self._camera, face_dir)
            )

    @abstractmethod
    def face_recognition(
        self, shared_frame: SharedFrame, detected_object: DetectedObject
    ) -> None:
        """Perform face recognition on detected object."""

    def process(self, post_processor_frame: PostProcessorFrame) -> None:
        """Process received frame."""
        for detected_object in post_processor_frame.filtered_objects:
            with post_processor_frame.shared_frame:
                self.face_recognition(
                    post_processor_frame.shared_frame, detected_object
                )

    def _insert_face_recognition_result(
        self, snapshot_path: str | None, face_dict: FaceDict
    ) -> None:
        """Insert object into database."""
        with self._storage.get_session() as session:
            stmt = insert(PostProcessorResults).values(
                camera_identifier=self._camera.identifier,
                domain=DOMAIN,
                snapshot_path=snapshot_path,
                data=face_dict.as_dict(),
            )
            session.execute(stmt)
            session.commit()

    def _save_face(
        self,
        face_dict: FaceDict,
        coordinates: tuple[int, int, int, int],
        shared_frame: SharedFrame,
    ) -> None:
        """Save face to disk and database."""
        snapshot_path = None
        if shared_frame:
            snapshot_path = self._camera.save_snapshot(
                shared_frame,
                DOMAIN,
                relative_coords=calculate_relative_coords(
                    coordinates, self._camera.resolution
                ),
                subfolder=face_dict.name,
            )
        self._insert_face_recognition_result(snapshot_path, face_dict)

    def known_face_found(
        self,
        face: str,
        coordinates: tuple[int, int, int, int],
        shared_frame: SharedFrame,
        confidence: float | None = None,
        extra_attributes: dict[str, Any] | None = None,
    ) -> None:
        """Adds/expires known faces."""
        # Cancel the expiry timer if face has already been detected
        if self._faces.get(face, None):
            self._faces[face].timer.cancel()

        # Adds a detected face and schedules an expiry timer
        face_dict = FaceDict(
            face,
            coordinates,
            confidence,
            Timer(self._config[CONFIG_EXPIRE_AFTER], self.expire_face, [face]),
            extra_attributes=extra_attributes,
        )
        face_dict.timer.start()

        # Only store face once until it is expired
        if self._faces.get(face, None) is None and self._config[CONFIG_SAVE_FACES]:
            self._save_face(face_dict, coordinates, shared_frame)

        self._vis.dispatch_event(
            EVENT_FACE_DETECTED.format(
                camera_identifier=self._camera.identifier, face=face
            ),
            EventFaceDetected(
                camera_identifier=self._camera.identifier,
                face=face_dict,
            ),
        )
        self._faces[face] = face_dict

    def unknown_face_found(
        self,
        coordinates: tuple[int, int, int, int],
        shared_frame: SharedFrame,
        confidence: float | None = None,
        extra_attributes: dict[str, Any] | None = None,
    ) -> None:
        """Save unknown faces."""
        face_dict = FaceDict(
            UNKNOWN_FACE,
            coordinates,
            confidence,
            Timer(self._config[CONFIG_EXPIRE_AFTER], self.expire_face, [UNKNOWN_FACE]),
            extra_attributes=extra_attributes,
        )

        if self._config[CONFIG_SAVE_UNKNOWN_FACES]:
            self._save_face(face_dict, coordinates, shared_frame)

    def expire_face(self, face) -> None:
        """Expire no longer found face."""
        self._logger.debug(f"Expiring face {face}")
        self._vis.dispatch_event(
            EVENT_FACE_EXPIRED.format(
                camera_identifier=self._camera.identifier, face=face
            ),
            EventFaceDetected(
                camera_identifier=self._camera.identifier,
                face=self._faces[face],
            ),
        )
        del self._faces[face]
