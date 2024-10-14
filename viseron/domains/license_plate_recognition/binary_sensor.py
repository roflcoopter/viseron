"""Binary sensor that represents a known license plate."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from viseron.domains.camera.entity.binary_sensor import CameraBinarySensor
from viseron.domains.license_plate_recognition.const import (
    EVENT_PLATE_DETECTED,
    EVENT_PLATE_EXPIRED,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.license_plate_recognition import (
        EventPlateDetected,
        LicensePlateRecognitionResult,
    )


class LicensePlateRecognitionBinarySensor(CameraBinarySensor):
    """Entity that keeps track of a known license plate."""

    def __init__(
        self,
        vis: Viseron,
        camera: AbstractCamera,
        plate: str,
    ) -> None:
        super().__init__(vis, camera)
        self._plate = plate
        self.object_id = f"{camera.identifier}_license_plate_detected_{plate}"
        self.name = f"{camera.name} License Plate Detected {plate.upper()}"
        self.icon = "mdi:car-search"

        self._result: LicensePlateRecognitionResult | None = None
        self._detected = False

    def setup(self) -> None:
        """Set up event listener."""
        self._vis.listen_event(
            EVENT_PLATE_DETECTED.format(
                camera_identifier=self._camera.identifier, plate=self._plate
            ),
            self.plate_detected,
        )
        self._vis.listen_event(
            EVENT_PLATE_EXPIRED.format(
                camera_identifier=self._camera.identifier, plate=self._plate
            ),
            self.plate_expired,
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

    def plate_detected(self, event_data: Event[EventPlateDetected]) -> None:
        """Handle license plate detected event."""
        self._detected = True
        self._result = event_data.data.plate
        self.set_state()

    def plate_expired(self) -> None:
        """Expire license plate after a given number of seconds."""
        self._detected = False
        self._result = None
        self.set_state()
