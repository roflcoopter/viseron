"""Image entity for the latest recognized face of a camera."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from viseron.domains.camera.entity.image import CameraImage

from .const import EVENT_FACE_DETECTED

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.face_recognition import EventFaceDetected


class LatestFaceImage(CameraImage):
    """Entity that keeps track of the latest recognized face snapshot of a camera."""

    def __init__(self, vis: Viseron, camera: AbstractCamera) -> None:
        super().__init__(vis, camera)
        self.device_class = "running"
        self.object_id = f"{camera.identifier}_latest_face_recognition"
        self.name = f"{camera.name} Latest Face Recognition"

        self._attr_face: str | None = None
        self._attr_confidence: float | None = None

    def setup(self) -> None:
        """Set up event listener."""
        self._event_listeners.append(
            self._vis.listen_event(
                EVENT_FACE_DETECTED.format(
                    camera_identifier=self._camera.identifier, face="*"
                ),
                self.handle_event,
            )
        )

    @property
    def extra_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return {
            "face": self._attr_face,
            "confidence": self._attr_confidence,
        }

    def handle_event(self, event_data: Event[EventFaceDetected]) -> None:
        """Handle face detected event.

        Only updates the image on a fresh appearance of a face, not on every
        re-detection of a face that is already being tracked.
        """
        face = event_data.data.face
        if event_data.data.image is None:
            return

        self._attr_face = face.name
        self._attr_confidence = face.confidence
        self._image = event_data.data.image
        self.set_state()
