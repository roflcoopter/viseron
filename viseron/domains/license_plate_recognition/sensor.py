"""Binary sensor that represents license plate recognition."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.const import STATE_UNKNOWN
from viseron.domains.camera.entity.sensor import CameraSensor

from .const import (
    EVENT_LICENSE_PLATE_RECOGNITION_EXPIRED,
    EVENT_LICENSE_PLATE_RECOGNITION_RESULT,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.license_plate_recognition import EventLicensePlateRecognition


class LicensePlateRecognitionSensor(CameraSensor):
    """Entity that keeps track of license plate recognition results."""

    def __init__(self, vis: Viseron, camera: AbstractCamera) -> None:
        super().__init__(vis, camera)
        self.object_id = f"{camera.identifier}_license_plate_recognition"
        self.name = f"{camera.name} License Plate Recognition Result"
        self.icon = "mdi:car-search"

        self._license_plate_recognition_event: EventLicensePlateRecognition | None = (
            None
        )

    def setup(self) -> None:
        """Set up event listener."""
        self._vis.listen_event(
            EVENT_LICENSE_PLATE_RECOGNITION_RESULT.format(
                camera_identifier=self._camera.identifier
            ),
            self.result,
        )
        self._vis.listen_event(
            EVENT_LICENSE_PLATE_RECOGNITION_EXPIRED.format(
                camera_identifier=self._camera.identifier
            ),
            self.result_expired,
        )

    @property
    def state(self):
        """Return entity state."""
        if (
            self._license_plate_recognition_event
            and self._license_plate_recognition_event.result
        ):
            return self._license_plate_recognition_event.result[0].plate
        return STATE_UNKNOWN

    @property
    def extra_attributes(self):
        """Return entity attributes."""
        if (
            self._license_plate_recognition_event
            and self._license_plate_recognition_event.result
        ):
            return {"result": self._license_plate_recognition_event.result}
        return {}

    def result(self, event_data: Event[EventLicensePlateRecognition]) -> None:
        """Handle license plate recognition result event."""
        self._license_plate_recognition_event = event_data.data
        self.set_state()

    def result_expired(self, _event_data: Event[EventLicensePlateRecognition]) -> None:
        """Handle license plate recognition expired event."""
        self._license_plate_recognition_event = None
        self.set_state()
