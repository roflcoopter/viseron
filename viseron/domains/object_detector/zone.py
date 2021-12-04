"""Handling of Zones within a cameras field of view."""
from __future__ import annotations

import logging
from typing import List

from viseron import Viseron
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.domains.object_detector.const import CONFIG_LABEL_LABEL
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.helpers import generate_numpy_from_coordinates, object_in_polygon
from viseron.helpers.filter import Filter

from .const import CONFIG_COORDINATES, CONFIG_LABELS, CONFIG_ZONE_NAME

EVENT_OBJECTS_IN_ZONE = "{camera_identifier}/zone/{zone_name}/objects"


class Zone:
    """Representation of a zone.

    Used to limit object detection to certain areas of a cameras field of view.
    Different objects can be searched for in different zones.
    """

    def __init__(
        self,
        vis: Viseron,
        camera_identifier,
        zone_config,
        mask,
    ):
        self._vis = vis
        self._camera = vis.get_registered_camera(camera_identifier)
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)

        self._coordinates = generate_numpy_from_coordinates(
            zone_config[CONFIG_COORDINATES]
        )
        self._camera_resolution = self._camera.resolution

        self._name = zone_config[CONFIG_ZONE_NAME]
        self._objects_in_zone: List[DetectedObject] = []
        self._object_filters = {}
        if zone_config[CONFIG_LABELS]:
            for object_filter in zone_config[CONFIG_LABELS]:
                self._object_filters[object_filter[CONFIG_LABEL_LABEL]] = Filter(
                    vis.get_registered_camera(camera_identifier).resolution,
                    object_filter,
                    mask,
                )
        else:
            self._logger.warning(
                "No labels configured. "
                f"No objects will be detected in zone {zone_config[CONFIG_ZONE_NAME]}"
            )

    def filter_zone(self, shared_frame: SharedFrame, objects: List[DetectedObject]):
        """Filter out objects to see if they are within the zone."""
        objects_in_zone = []
        for obj in objects:
            if self._object_filters.get(obj.label) and self._object_filters[
                obj.label
            ].filter_object(obj):
                if object_in_polygon(self._camera_resolution, obj, self._coordinates):
                    obj.relevant = True
                    objects_in_zone.append(obj)

                    if self._object_filters[obj.label].trigger_recorder:
                        obj.trigger_recorder = True

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
    def objects_in_zone(self):
        """Return all present objects in the zone."""
        return self._objects_in_zone

    def objects_in_zone_setter(
        self, shared_frame: SharedFrame, objects: List[DetectedObject]
    ):
        """Set objects in zone."""
        if objects == self._objects_in_zone:
            return

        self._objects_in_zone = objects
        self._vis.dispatch_event(
            EVENT_OBJECTS_IN_ZONE.format(
                camera_identifier=self._camera.identifier, zone_name=self._name
            ),
            {
                "camera_identifier": self._camera.identifier,
                "shared_frame": shared_frame,
                "zone": self,
                "objects": objects,
            },
        )

    @property
    def name(self) -> str:
        """Return name of zone."""
        return self._name
