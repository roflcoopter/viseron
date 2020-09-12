import logging
from typing import List

import cv2
from lib.detector import DetectedObject
from lib.helpers import Filter, calculate_absolute_coords
from lib.mqtt.binary_sensor import MQTTBinarySensor

LOGGER = logging.getLogger(__name__)


class Zone:
    def __init__(self, zone, camera_resolution, config, mqtt_queue):
        self._coordinates = zone["coordinates"]
        self._camera_resolution = camera_resolution
        self.config = config
        self._mqtt_queue = mqtt_queue
        self._zone = zone

        self._objects_in_zone = []
        self._labels_in_zone = []
        self._object_filters = {}
        zone_labels = (
            zone["labels"] if zone["labels"] else config.object_detection.labels
        )
        for object_filter in zone_labels:
            self._object_filters[object_filter.label] = Filter(object_filter)

        self._mqtt_devices = {}
        if self._mqtt_queue:
            self._mqtt_devices["zone"] = MQTTBinarySensor(
                config, mqtt_queue, zone["name"]
            )
            for label in zone_labels:
                self._mqtt_devices[label.label] = MQTTBinarySensor(
                    config, mqtt_queue, f"{zone['name']} {label.label}"
                )

    def filter_zone(self, objects: List[DetectedObject]):
        objects_in_zone = []
        labels_in_zone = []
        for obj in objects:
            if self._object_filters.get(obj.label) and self._object_filters[
                obj.label
            ].filter_object(obj):
                x1, _, x2, y2 = calculate_absolute_coords(
                    (obj.rel_x1, obj.rel_y1, obj.rel_x2, obj.rel_y2,),
                    self._camera_resolution,
                )
                middle = ((x2 - x1) / 2) + x1
                if cv2.pointPolygonTest(self.coordinates, (middle, y2), False) >= 0:
                    obj.relevant = True
                    objects_in_zone.append(obj)
                    if obj.label not in labels_in_zone:
                        labels_in_zone.append(obj.label)

        self.objects_in_zone = objects_in_zone
        self.labels_in_zone = labels_in_zone

    def on_connect(self, client):
        for device in self._mqtt_devices.values():
            device.on_connect(client)

    @property
    def coordinates(self):
        return self._coordinates

    @property
    def objects_in_zone(self):
        return self._objects_in_zone

    @objects_in_zone.setter
    def objects_in_zone(self, value):
        if value == self._objects_in_zone:
            return

        self._objects_in_zone = value
        if self._mqtt_queue:
            self._mqtt_devices["zone"].publish(bool(value))

    @property
    def labels_in_zone(self):
        return self._objects_in_zone

    @labels_in_zone.setter
    def labels_in_zone(self, labels_in_zone):
        if labels_in_zone == self._labels_in_zone:
            return

        labels_added = list(set(labels_in_zone) - set(self._labels_in_zone))
        labels_removed = list(set(self._labels_in_zone) - set(labels_in_zone))

        if self._mqtt_queue:
            for label in labels_added:
                self._mqtt_devices[label].publish(True)
            for label in labels_removed:
                self._mqtt_devices[label].publish(False)

        self._labels_in_zone = labels_in_zone
