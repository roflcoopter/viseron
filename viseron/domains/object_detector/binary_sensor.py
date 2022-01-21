"""Binary sensor that represents object detection."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from viseron.domains.camera.entity.binary_sensor import CameraBinarySensor

from .const import EVENT_OBJECTS_IN_FOV, EVENT_OBJECTS_IN_ZONE

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import AbstractCamera

    from .detected_object import DetectedObject
    from .zone import Zone


class ObjectDetectedBinarySensor(CameraBinarySensor):
    """Entity that keeps track of object detection."""

    def __init__(
        self,
        vis: Viseron,
        camera: AbstractCamera,
    ):
        super().__init__(vis, camera)
        self._objects: List[DetectedObject] = []

    @property
    def _is_on(self):
        return bool(self._objects)

    def handle_event(self, event_data: Event):
        """Handle status event."""
        if self._is_on == bool(event_data.data.objects):
            return

        self._objects = event_data.data.objects
        self.set_state()


class ObjectDetectedBinarySensorFoV(ObjectDetectedBinarySensor):
    """Entity that keeps track of object detection in field of view."""

    def __init__(
        self,
        vis: Viseron,
        camera: AbstractCamera,
    ):
        super().__init__(vis, camera)
        self.object_id = f"{camera.identifier}_object_detected"
        self.name = f"{camera.name} Object Detected"

        vis.listen_event(
            EVENT_OBJECTS_IN_FOV.format(camera_identifier=camera.identifier),
            self.handle_event,
        )


class ObjectDetectedBinarySensorZone(ObjectDetectedBinarySensor):
    """Entity that keeps track of object detection in a zone."""

    def __init__(
        self,
        vis: Viseron,
        zone: Zone,
        camera: AbstractCamera,
    ):
        super().__init__(vis, camera)
        self.object_id = f"{camera.identifier}_zone_{zone.name}_object_detected"
        self.name = f"{camera.name} Zone {zone.name} Object Detected"

        vis.listen_event(
            EVENT_OBJECTS_IN_ZONE.format(
                camera_identifier=camera.identifier, zone_name=zone.name
            ),
            self.handle_event,
        )


class ObjectDetectedBinarySensorLabel(CameraBinarySensor):
    """Entity that keeps track of object detection for a label."""

    def __init__(
        self,
        vis: Viseron,
        label: str,
        camera: AbstractCamera,
    ):
        super().__init__(vis, camera)
        self._label = label

        self._tracked_label: List[DetectedObject] = []
        self._reported_count = 0

    @property
    def _is_on(self):
        return bool(self._tracked_label)

    @property
    def attributes(self):
        """Return entity attributes."""
        return {"count": len(self._tracked_label)}

    def handle_event(self, event_data: Event):
        """Handle status event."""
        tracked_label = [
            label for label in event_data.data.objects if label.label == self._label
        ]

        count = len(tracked_label)
        if self._is_on == bool(tracked_label) and self._reported_count == count:
            return

        self._tracked_label = tracked_label
        self._reported_count = count
        self.set_state()


class ObjectDetectedBinarySensorFoVLabel(ObjectDetectedBinarySensorLabel):
    """Entity that keeps track of object detection for a label in field of view."""

    def __init__(
        self,
        vis: Viseron,
        label: str,
        camera: AbstractCamera,
    ):
        super().__init__(vis, label, camera)
        self.object_id = f"{camera.identifier}_object_detected_{label}"
        self.name = f"{camera.name} Object Detected {label.capitalize()}"

        vis.listen_event(
            EVENT_OBJECTS_IN_FOV.format(camera_identifier=camera.identifier),
            self.handle_event,
        )


class ObjectDetectedBinarySensorZoneLabel(ObjectDetectedBinarySensorLabel):
    """Entity that keeps track of object detection for a label in a zone."""

    def __init__(
        self,
        vis: Viseron,
        zone: Zone,
        label: str,
        camera: AbstractCamera,
    ):
        super().__init__(vis, label, camera)
        self.object_id = f"{camera.identifier}_zone_{zone.name}_object_detected_{label}"
        self.name = (
            f"{camera.name} Zone {zone.name} Object Detected {label.capitalize()}"
        )

        vis.listen_event(
            EVENT_OBJECTS_IN_ZONE.format(
                camera_identifier=camera.identifier, zone_name=zone.name
            ),
            self.handle_event,
        )
