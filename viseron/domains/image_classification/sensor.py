"""Binary sensor that represents image classification."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.const import STATE_UNKNOWN
from viseron.domains.camera.entity.sensor import CameraSensor

from .const import EVENT_IMAGE_CLASSIFICATION_EXPIRED, EVENT_IMAGE_CLASSIFICATION_RESULT

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.image_classification import EventImageClassification


class ImageClassificationSensor(CameraSensor):
    """Entity that keeps track of image classification results."""

    def __init__(self, vis: Viseron, camera: AbstractCamera):
        super().__init__(vis, camera)
        self.object_id = f"{camera.identifier}_image_classification"
        self.name = f"{camera.name} Image Classification"
        self.icon = "mdi:magnify-scan"

        self._image_classification_event: EventImageClassification | None = None

        vis.listen_event(
            EVENT_IMAGE_CLASSIFICATION_RESULT.format(
                camera_identifier=camera.identifier
            ),
            self.result,
        )
        vis.listen_event(
            EVENT_IMAGE_CLASSIFICATION_EXPIRED.format(
                camera_identifier=camera.identifier
            ),
            self.result_expired,
        )

    @property
    def state(self):
        """Return entity state."""
        if self._image_classification_event and self._image_classification_event.result:
            return self._image_classification_event.result[0].label
        return STATE_UNKNOWN

    @property
    def attributes(self):
        """Return entity attributes."""
        if self._image_classification_event and self._image_classification_event.result:
            return {"result": self._image_classification_event.result}
        return {}

    def result(self, event_data: Event):
        """Handle image classification result event."""
        self._image_classification_event = event_data.data
        self.set_state()

    def result_expired(self, _event_data: Event):
        """Handle image classification expired event."""
        self._image_classification_event = None
        self.set_state()
