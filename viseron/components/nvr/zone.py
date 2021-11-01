"""Handling of Zones within a cameras field of view."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

from viseron import Viseron, helpers
from viseron.components.nvr.const import (
    CONFIG_COORDINATES,
    CONFIG_MASK,
    CONFIG_ZONE_LABELS,
    CONFIG_ZONE_NAME,
)
from viseron.domains.camera import DOMAIN as CAMERA_DOMAIN
from viseron.helpers.filter import Filter

if TYPE_CHECKING:
    from viseron.camera.frame import Frame
    from viseron.domains.object_detector.detected_object import DetectedObject

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
        nvr_config,
        zone_config,
    ):
        self._vis = vis
        self._camera = vis.data[CAMERA_DOMAIN][camera_identifier]
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)

        self._coordinates = zone_config[CONFIG_COORDINATES]
        self._camera_resolution = self._camera.resolution

        self._name = zone_config[CONFIG_ZONE_NAME]
        self._objects_in_zone: List[DetectedObject] = []
        self._object_filters = {}
        for object_filter in zone_config[CONFIG_ZONE_LABELS]:
            self._object_filters[object_filter.label] = Filter(
                self._camera_resolution, object_filter, nvr_config[CONFIG_MASK]
            )

    def filter_zone(self, frame: Frame):
        """Filter out objects to see if they are within the zone."""
        objects_in_zone = []
        for obj in frame.objects:
            if self._object_filters.get(obj.label) and self._object_filters[
                obj.label
            ].filter_object(obj):
                if helpers.object_in_polygon(
                    self._camera_resolution, obj, self.coordinates
                ):
                    obj.relevant = True
                    objects_in_zone.append(obj)

                    if self._object_filters[obj.label].trigger_recorder:
                        obj.trigger_recorder = True

        self.objects_in_zone = objects_in_zone

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

    @objects_in_zone.setter
    def objects_in_zone(self, objects):
        if objects == self._objects_in_zone:
            return

        self._objects_in_zone = objects
        self._vis.dispatch_event(
            EVENT_OBJECTS_IN_ZONE.format(
                camera_identifier=self._camera.identifier, zone_name=self._name
            ),
            {"zone": self, "objects": objects},
        )

    @property
    def name(self) -> str:
        """Return name of zone."""
        return self._name
