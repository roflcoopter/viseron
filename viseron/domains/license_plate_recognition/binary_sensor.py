"""Binary sensor that represents a known license plate."""
from __future__ import annotations

from threading import Timer
from typing import TYPE_CHECKING, Any

from viseron.domains.camera.entity.binary_sensor import CameraBinarySensor
from viseron.domains.license_plate_recognition.const import (
    EVENT_LICENSE_PLATE_RECOGNITION_RESULT,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.license_plate_recognition import (
        EventLicensePlateRecognition,
        LicensePlateRecognitionResult,
    )


class LicensePlateRecognitionBinarySensor(CameraBinarySensor):
    """Entity that keeps track of a known license plate."""

    def __init__(
        self, vis: Viseron, camera: AbstractCamera, plate: str, expire_after: int
    ) -> None:
        super().__init__(vis, camera)
        self._plate = plate
        self._expire_after = expire_after
        self.object_id = f"{camera.identifier}_license_plate_detected_{plate}"
        self.name = f"{camera.name} License Plate Detected {plate.upper()}"
        self.icon = "mdi:car-search"

        self._expire_timer: Timer | None = None
        self._result: LicensePlateRecognitionResult | None = None
        self._detected = False

    def setup(self) -> None:
        """Set up event listener."""
        self._vis.listen_event(
            EVENT_LICENSE_PLATE_RECOGNITION_RESULT.format(
                camera_identifier=self._camera.identifier
            ),
            self.plate_detected,
        )

    @property
    def _is_on(self):
        return self._detected

    @property
    def extra_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        attributes: dict[str, Any] = {}
        attributes["camera_identifier"] = self._camera.identifier
        attributes["camera_name"] = self._camera.name
        attributes["plate"] = self._plate
        attributes["detected"] = self._detected
        if self._result:
            attributes["confidence"] = self._result.confidence
        return {}

    def plate_detected(self, event_data: Event[EventLicensePlateRecognition]) -> None:
        """Handle license plate detected event."""
        if not event_data.data.result:
            return

        for plate in event_data.data.result:
            if plate.plate != self._plate:
                continue

            if self._expire_timer:
                self._expire_timer.cancel()

            self._detected = True
            self._result = plate
            self._expire_timer = Timer(
                self._expire_after,
                self._expire_plate,
            )
            self._expire_timer.start()
            self.set_state()
            return

    def _expire_plate(self) -> None:
        """Expire license plate after a given number of seconds."""
        self._detected = False
        self._result = None
        self.set_state()
