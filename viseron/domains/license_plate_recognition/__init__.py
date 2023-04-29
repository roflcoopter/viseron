"""License plate recognition module."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from threading import Timer
from typing import TYPE_CHECKING, Any

import numpy as np
import voluptuous as vol

from viseron.domains.license_plate_recognition.binary_sensor import (
    LicensePlateRecognitionBinarySensor,
)
from viseron.domains.post_processor import BASE_CONFIG_SCHEMA, AbstractPostProcessor
from viseron.helpers.schemas import FLOAT_MIN_ZERO, FLOAT_MIN_ZERO_MAX_ONE

from .const import (
    CONFIG_EXPIRE_AFTER,
    CONFIG_KNOWN_PLATES,
    CONFIG_MIN_CONFIDENCE,
    DEFAULT_EXPIRE_AFTER,
    DEFAULT_KNOWN_PLATES,
    DEFAULT_MIN_CONFIDENCE,
    DESC_EXPIRE_AFTER,
    DESC_KNOWN_PLATES,
    DESC_MIN_CONFIDENCE,
    EVENT_LICENSE_PLATE_RECOGNITION_EXPIRED,
    EVENT_LICENSE_PLATE_RECOGNITION_RESULT,
)
from .sensor import LicensePlateRecognitionSensor

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.post_processor import PostProcessorFrame


BASE_CONFIG_SCHEMA = BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_KNOWN_PLATES,
            default=DEFAULT_KNOWN_PLATES,
            description=DESC_KNOWN_PLATES,
        ): [str],
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
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class LicensePlateRecognitionResult:
    """Object that holds information on license plate recognition."""

    camera_identifier: str
    plate: str
    confidence: float
    known: bool

    def as_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "camera_identifier": self.camera_identifier,
            "plate": self.plate,
            "confidence": round(float(self.confidence), 3),
            "known": self.known,
        }


@dataclass
class EventLicensePlateRecognition:
    """Hold information on license plate recognition event."""

    camera_identifier: str
    result: list[LicensePlateRecognitionResult] | None


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
        vis.add_entity(component, LicensePlateRecognitionSensor(vis, self._camera))
        for plate in self._config[CONFIG_KNOWN_PLATES]:
            vis.add_entity(
                component,
                LicensePlateRecognitionBinarySensor(
                    vis, self._camera, plate, self._config[CONFIG_EXPIRE_AFTER]
                ),
            )

    @abstractmethod
    def preprocess(self, post_processor_frame: PostProcessorFrame) -> np.ndarray:
        """Perform preprocessing of frame before running recognition."""

    @abstractmethod
    def license_plate_recognition(
        self, frame: np.ndarray, post_processor_frame: PostProcessorFrame
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
                    self._camera.identifier,
                    plate.plate,
                    plate.confidence,
                    plate.plate in self._config[CONFIG_KNOWN_PLATES],
                )
            )

        return _result

    def process(self, post_processor_frame: PostProcessorFrame) -> None:
        """Process frame and run license plate recognition.

        If at least one plate is found, an event is dispatched, and a timer is started
        to expire the result after a given number of seconds.
        """
        preprocessed_frame = self.preprocess(post_processor_frame)
        result = self._process_result(
            self.license_plate_recognition(preprocessed_frame, post_processor_frame)
        )

        if result is None:
            return

        # We have a result, cancel any existing expiry timer
        if self._expire_timer:
            self._expire_timer.cancel()

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
                self._config[CONFIG_EXPIRE_AFTER], self.expire_result, (result,)
            )
            self._expire_timer.start()

    def expire_result(self, result: LicensePlateRecognitionResult) -> None:
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
