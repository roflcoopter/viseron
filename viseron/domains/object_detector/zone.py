"""Handling of Zones within a cameras field of view."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.domains.object_detector.const import CONFIG_LABEL_LABEL
from viseron.domains.object_detector.detected_object import EventDetectedObjectsData
from viseron.helpers import generate_numpy_from_coordinates, object_in_polygon
from viseron.helpers.filter import Filter

from .binary_sensor import (
    ObjectDetectedBinarySensorZone,
    ObjectDetectedBinarySensorZoneLabel,
)
from .const import (
    CONFIG_COORDINATES,
    CONFIG_LABELS,
    CONFIG_ZONE_NAME,
    EVENT_OBJECTS_IN_ZONE,
)

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.camera.shared_frames import SharedFrame
    from viseron.domains.object_detector.detected_object import DetectedObject


class Zone:
    """Representation of a zone.

    Used to limit object detection to certain areas of a cameras field of view.
    Different objects can be searched for in different zones.
    """

    def __init__(
        self,
        vis: Viseron,
        component: str,
        camera_identifier: str,
        zone_config: dict[str, Any],
        mask: list,
    ) -> None:
        self._vis = vis
        self._camera = vis.get_registered_domain(CAMERA_DOMAIN, camera_identifier)
        self._zone_config = zone_config
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)

        self._coordinates = generate_numpy_from_coordinates(
            zone_config[CONFIG_COORDINATES]
        )
        self._camera_resolution = self._camera.resolution

        self._name: str = zone_config[CONFIG_ZONE_NAME]
        self._objects_in_zone: list[DetectedObject] = []
        self._object_filters: dict[str, Filter] = {}
        if zone_config[CONFIG_LABELS]:
            for object_filter in zone_config[CONFIG_LABELS]:
                self._object_filters[object_filter[CONFIG_LABEL_LABEL]] = Filter(
                    self._camera.resolution,
                    object_filter,
                    mask,
                )
                vis.add_entity(
                    component,
                    ObjectDetectedBinarySensorZoneLabel(
                        vis, self, object_filter[CONFIG_LABEL_LABEL], self._camera
                    ),
                )

        else:
            self._logger.warning(
                "No labels configured. "
                f"No objects will be detected in zone {zone_config[CONFIG_ZONE_NAME]}"
            )
        vis.add_entity(
            component,
            ObjectDetectedBinarySensorZone(vis, self, self._camera),
        )

    def filter_zone(
        self, shared_frame: SharedFrame, objects: list[DetectedObject]
    ) -> None:
        """Filter out objects to see if they are within the zone."""
        objects_in_zone = []
        for obj in objects:
            if self._object_filters.get(obj.label) and self._object_filters[
                obj.label
            ].filter_object(obj):
                if object_in_polygon(self._camera_resolution, obj, self._coordinates):
                    obj.relevant = True
                    objects_in_zone.append(obj)

                    if self._object_filters[obj.label].trigger_event_recording:
                        obj.trigger_event_recording = True
                    self._object_filters[obj.label].should_store(obj)

        self.objects_in_zone_setter(shared_frame, objects_in_zone)

    @property
    def coordinates(self):
        """Return zone coordinates."""
        return self._coordinates

    @property
    def object_filters(self):
        """Return zone object filters."""
        return self._object_filters

    @property
    def objects_in_zone(self) -> list[DetectedObject]:
        """Return all present objects in the zone."""
        return self._objects_in_zone

    def objects_in_zone_setter(
        self, shared_frame: SharedFrame | None, objects: list[DetectedObject]
    ) -> None:
        """Set objects in zone."""
        if objects == self._objects_in_zone:
            return

        self._objects_in_zone = objects
        self._vis.dispatch_event(
            EVENT_OBJECTS_IN_ZONE.format(
                camera_identifier=self._camera.identifier, zone_name=self._name
            ),
            EventDetectedObjectsData(
                camera_identifier=self._camera.identifier,
                shared_frame=shared_frame,
                objects=objects,
                zone=self,
            ),
        )

    @property
    def name(self) -> str:
        """Return name of zone."""
        return self._name

    def as_dict(self) -> dict[str, Any]:
        """Return zone as dict."""
        return {
            "coordinates": self._zone_config,
            "name": self._name,
            "camera_identifier": self._camera.identifier,
        }
