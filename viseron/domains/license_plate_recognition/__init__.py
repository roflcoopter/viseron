"""License plate recognition module."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from threading import Timer
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from viseron.domains.license_plate_recognition.binary_sensor import (
    LicensePlateRecognitionBinarySensor,
)
from viseron.domains.post_processor import BASE_CONFIG_SCHEMA, AbstractPostProcessor
from viseron.events import EventData
from viseron.helpers.schemas import FLOAT_MIN_ZERO, FLOAT_MIN_ZERO_MAX_ONE
from viseron.types import SnapshotDomain

from .const import (
    CONFIG_EXPIRE_AFTER,
    CONFIG_KNOWN_PLATES,
    CONFIG_MIN_CONFIDENCE,
    CONFIG_SAVE_PLATES,
    DEFAULT_EXPIRE_AFTER,
    DEFAULT_KNOWN_PLATES,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_SAVE_PLATES,
    DESC_EXPIRE_AFTER,
    DESC_KNOWN_PLATES,
    DESC_MIN_CONFIDENCE,
    DESC_SAVE_PLATES,
    DOMAIN,
    EVENT_LICENSE_PLATE_RECOGNITION_EXPIRED,
    EVENT_LICENSE_PLATE_RECOGNITION_RESULT,
    EVENT_PLATE_DETECTED,
    EVENT_PLATE_EXPIRED,
)
from .sensor import LicensePlateRecognitionSensor

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.camera.shared_frames import SharedFrame
    from viseron.domains.object_detector.detected_object import DetectedObject
    from viseron.domains.post_processor import PostProcessorFrame


BASE_CONFIG_SCHEMA = BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_KNOWN_PLATES,
            default=DEFAULT_KNOWN_PLATES,
            description=DESC_KNOWN_PLATES,
        ): [str],
        vol.Optional(
            CONFIG_SAVE_PLATES,
            default=DEFAULT_SAVE_PLATES,
            description=DESC_SAVE_PLATES,
        ): bool,
        vol.Optional(
            CONFIG_MIN_CONFIDENCE,
            default=DEFAULT_MIN_CONFIDENCE,
            description=DESC_MIN_CONFIDENCE,
        ): FLOAT_MIN_ZERO_MAX_ONE,
        vol.Optional(
            CONFIG_EXPIRE_AFTER,
            default=DEFAULT_EXPIRE_AFTER,
            description=DESC_EXPIRE_AFTER,
        ): FLOAT_MIN_ZERO,
    }
)


@dataclass
class DetectedLicensePlate:
    """Object that holds information on a detected license plate."""

    plate: str
    confidence: float
    rel_x1: float
    rel_y1: float
    rel_x2: float
    rel_y2: float
    detected_object: DetectedObject


@dataclass
class LicensePlateRecognitionResult:
    """Object that holds information on license plate recognition."""

    camera_identifier: str
    plate: str
    confidence: float
    rel_coordinates: tuple[float, float, float, float]
    known: bool
    timer: Timer
    detected_object: DetectedObject

    def as_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "camera_identifier": self.camera_identifier,
            "plate": self.plate,
            "confidence": round(float(self.confidence), 3),
            "rel_coordinates": self.rel_coordinates,
            "known": self.known,
        }


@dataclass
class EventLicensePlateRecognition(EventData):
    """Hold information on license plate recognition event."""

    camera_identifier: str
    result: list[LicensePlateRecognitionResult] | None

    def as_dict(self) -> dict[str, Any]:
        """Return as dict."""
        return {
            "camera_identifier": self.camera_identifier,
            "result": [plate.as_dict() for plate in self.result] if self.result else [],
        }


@dataclass
class EventPlateDetected(EventData):
    """Hold information on plate detection event."""

    camera_identifier: str
    plate: LicensePlateRecognitionResult

    def as_dict(self) -> dict[str, Any]:
        """Return as dict."""
        return {
            "camera_identifier": self.camera_identifier,
            "plate": self.plate.as_dict(),
        }


class AbstractLicensePlateRecognition(AbstractPostProcessor):
    """Abstract license plate recognition."""

    def __init__(
        self,
        vis: Viseron,
        component: str,
        config: dict[str, Any],
        camera_identifier: str,
    ) -> None:
        super().__init__(vis, config, camera_identifier)
        self._expire_timer: Timer | None = None
        self._plates: dict[str, LicensePlateRecognitionResult] = {}
        vis.add_entity(component, LicensePlateRecognitionSensor(vis, self._camera))
        for plate in self._config[CONFIG_KNOWN_PLATES]:
            vis.add_entity(
                component,
                LicensePlateRecognitionBinarySensor(vis, self._camera, plate),
            )

    def __post_init__(self, *args, **kwargs):
        """Post init hook."""
        self._vis.register_domain(DOMAIN, self._camera_identifier, self)

    @abstractmethod
    def license_plate_recognition(
        self, post_processor_frame: PostProcessorFrame
    ) -> list[DetectedLicensePlate]:
        """Perform license plate recognition."""

    def _process_result(
        self, result: list[DetectedLicensePlate]
    ) -> list[LicensePlateRecognitionResult] | None:
        """Process result from license plate recognition."""
        if not result:
            return None

        _result = []
        for plate in result:
            _result.append(
                LicensePlateRecognitionResult(
                    camera_identifier=self._camera.identifier,
                    plate=plate.plate,
                    confidence=plate.confidence,
                    rel_coordinates=(
                        plate.rel_x1,
                        plate.rel_y1,
                        plate.rel_x2,
                        plate.rel_y2,
                    ),
                    known=plate.plate in self._config[CONFIG_KNOWN_PLATES],
                    timer=Timer(
                        self._config[CONFIG_EXPIRE_AFTER],
                        self._expire_plate,
                        [plate.plate],
                    ),
                    detected_object=plate.detected_object,
                )
            )

        return _result

    def _save_plate(
        self, plate: LicensePlateRecognitionResult, shared_frame: SharedFrame
    ) -> None:
        """Save plate to disk and database."""
        snapshot_path = None
        if shared_frame:
            snapshot_path = self._camera.save_snapshot(
                shared_frame=shared_frame,
                domain=SnapshotDomain.LICENSE_PLATE_RECOGNITION,
                zoom_coordinates=plate.detected_object.rel_coordinates,
                bbox=plate.rel_coordinates,
                text=f"{plate.plate} {int(plate.confidence * 100)}%",
            )
        self._insert_result(DOMAIN, snapshot_path, plate.as_dict())

    def _plate_detected(
        self, plate: LicensePlateRecognitionResult, shared_frame: SharedFrame
    ) -> None:
        """Handle plate detected event."""
        self._logger.debug(f"Plate detected: {plate.plate}")
        # Cancel the expiry timer if plate has already been detected
        if self._plates.get(plate.plate, None):
            self._plates[plate.plate].timer.cancel()

        # Schedules an expiry timer
        plate.timer.start()

        # Only store plate once until it is expired
        if (
            self._plates.get(plate.plate, None) is None
            and self._config[CONFIG_SAVE_PLATES]
        ):
            self._save_plate(plate, shared_frame)

        self._vis.dispatch_event(
            EVENT_PLATE_DETECTED.format(
                camera_identifier=self._camera.identifier, plate=plate.plate
            ),
            EventPlateDetected(
                camera_identifier=self._camera.identifier,
                plate=plate,
            ),
        )
        self._plates[plate.plate] = plate

    def process(self, post_processor_frame: PostProcessorFrame) -> None:
        """Process frame and run license plate recognition.

        If at least one plate is found, an event is dispatched, and a timer is started
        to expire the result after a given number of seconds.
        """
        result = self._process_result(
            self.license_plate_recognition(post_processor_frame)
        )

        if result is None:
            return

        # We have a result, cancel any existing expiry timer
        if self._expire_timer:
            self._expire_timer.cancel()

        # Save plate if it is not already saved
        for plate in result:
            self._plate_detected(plate, post_processor_frame.shared_frame)

        self._vis.dispatch_event(
            EVENT_LICENSE_PLATE_RECOGNITION_RESULT.format(
                camera_identifier=self._camera.identifier
            ),
            EventLicensePlateRecognition(
                camera_identifier=self._camera.identifier,
                result=result,
            ),
        )
        if self._config[CONFIG_EXPIRE_AFTER] and result:
            self._expire_timer = Timer(
                self._config[CONFIG_EXPIRE_AFTER], self._expire_result, (result,)
            )
            self._expire_timer.start()

    def _expire_result(self, result: LicensePlateRecognitionResult) -> None:
        """Expire result after a given number of seconds."""
        self._logger.debug(f"Expiring license plate recognition result {result}")
        self._vis.dispatch_event(
            EVENT_LICENSE_PLATE_RECOGNITION_EXPIRED.format(
                camera_identifier=self._camera.identifier, result=result
            ),
            EventLicensePlateRecognition(
                camera_identifier=self._camera.identifier,
                result=None,
            ),
        )

    def _expire_plate(self, plate) -> None:
        """Expire no longer found plate."""
        self._logger.debug(f"Expiring plate {plate}")
        self._vis.dispatch_event(
            EVENT_PLATE_EXPIRED.format(
                camera_identifier=self._camera.identifier, plate=plate
            ),
            EventPlateDetected(
                camera_identifier=self._camera.identifier,
                plate=self._plates[plate],
            ),
        )
        del self._plates[plate]
