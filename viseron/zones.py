"""Handling of Zones within a cameras field of view."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import viseron.mqtt
from viseron import helpers
from viseron.const import TOPIC_FRAME_SCAN_POSTPROC
from viseron.data_stream import DataStream
from viseron.helpers.filter import Filter
from viseron.mqtt.binary_sensor import MQTTBinarySensor
from viseron.post_processors import PostProcessorFrame

if TYPE_CHECKING:
    from viseron.camera.frame import Frame
    from viseron.config import NVRConfig
    from viseron.detector.detected_object import DetectedObject


class Zone:
    """Representation of a zone.

    Used to limit object detection to certain areas of a cameras field of view.
    Different objects can be searched for in different zones.
    """

    def __init__(
        self,
        zone: Dict[str, Any],
        camera_resolution: Tuple[int, int],
        config: NVRConfig,
    ):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)

        self._coordinates = zone["coordinates"]
        self._camera_resolution = camera_resolution
        self._config = config

        self._name = zone["name"]
        self._objects_in_zone: List[DetectedObject] = []
        self._labels_in_zone: List[str] = []
        self._reported_label_count: Dict[str, int] = {}
        self._object_filters = {}
        zone_labels = (
            zone["labels"] if zone["labels"] else config.object_detection.labels
        )
        for object_filter in zone_labels:
            self._object_filters[object_filter.label] = Filter(
                config, camera_resolution, object_filter
            )

        self._mqtt_devices = {}
        if viseron.mqtt.MQTT.client:
            self._mqtt_devices["zone"] = MQTTBinarySensor(config, zone["name"])
            for label in zone_labels:
                self._mqtt_devices[label.label] = MQTTBinarySensor(
                    config, f"{zone['name']} {label.label}"
                )

        self._post_processor_topic = (
            f"{config.camera.name_slug}/{TOPIC_FRAME_SCAN_POSTPROC}",
        )

    def filter_zone(self, frame: Frame):
        """Filter out objects to see if they are within the zone."""
        objects_in_zone = []
        labels_in_zone = []
        for obj in frame.objects:
            if self._object_filters.get(obj.label) and self._object_filters[
                obj.label
            ].filter_object(obj):
                if helpers.object_in_polygon(
                    self._camera_resolution, obj, self.coordinates
                ):
                    obj.relevant = True
                    objects_in_zone.append(obj)

                    if obj.label not in labels_in_zone:
                        labels_in_zone.append(obj.label)

                    if self._object_filters[obj.label].trigger_recorder:
                        obj.trigger_recorder = True

                    if self._object_filters[obj.label].post_processor:
                        DataStream.publish_data(
                            (
                                f"{self._post_processor_topic}/"
                                f"{self._object_filters[obj.label].post_processor}"
                            ),
                            PostProcessorFrame(self._config, frame, obj, self),
                        )

        self.objects_in_zone = objects_in_zone
        self.labels_in_zone = labels_in_zone

    def on_connect(self):
        """On established MQTT connection."""
        for device in self._mqtt_devices.values():
            device.on_connect()

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
        if viseron.mqtt.MQTT.client:
            attributes = {}
            attributes["objects"] = [obj.formatted for obj in objects]
            self._mqtt_devices["zone"].publish(bool(objects), attributes)

    @property
    def labels_in_zone(self):
        """Return all present labels in the zone."""
        return self._objects_in_zone

    @labels_in_zone.setter
    def labels_in_zone(self, labels):
        self._labels_in_zone, self._reported_label_count = helpers.report_labels(
            labels,
            self._labels_in_zone,
            self._reported_label_count,
            self._mqtt_devices,
        )

    @property
    def name(self) -> str:
        """Return name of zone."""
        return self._name
