import logging

import cv2
from lib.helpers import Filter, calculate_absolute_coords
from lib.mqtt.binary_sensor import MQTTBinarySensor

LOGGER = logging.getLogger(__name__)


class ZoneLabelBinarySensor(MQTTBinarySensor):
    def __init__(self, config, name, label):
        super().__init__(config, f"{name} {label}")
        self._name = name
        self._label = label

    @property
    def base_topic(self):
        return (
            f"{self.config.mqtt.discovery_prefix}/binary_sensor/"
            f"{self.config.camera.mqtt_name}/{self._name}_{self._label}"
        )


class ZoneBinarySensor(MQTTBinarySensor):
    def __init__(self, config, name):
        super().__init__(config, name)
        self._name = name

    @property
    def base_topic(self):
        return (
            f"{self.config.mqtt.discovery_prefix}/binary_sensor/"
            f"{self.config.camera.mqtt_name}/{self._name}"
        )


class Zone:
    def __init__(self, zone, camera_resolution, config):
        LOGGER.debug(f"Zone: {zone}")
        self._coordinates = zone["coordinates"]
        self._camera_resolution = camera_resolution
        self.config = config
        self._objects_in_zone = []
        self._object_filters = {}
        zone_labels = (
            zone["labels"] if zone["labels"] else config.object_detection.labels
        )
        for object_filter in zone_labels:
            self._object_filters[object_filter.label] = Filter(object_filter)
        self._mqtt_devices = {}
        self._mqtt_devices["zone"] = ZoneBinarySensor(config, zone["name"])
        for label in zone_labels:
            self._mqtt_devices[label] = ZoneLabelBinarySensor(
                config, zone["name"], label.label
            )

    def filter_zone(self, objects):
        self._objects_in_zone = []
        for obj in objects:
            if self._object_filters.get(obj["label"]) and self._object_filters[
                obj["label"]
            ].filter_object(obj):
                x1, _, x2, y2 = calculate_absolute_coords(
                    (
                        obj["relative_x1"],
                        obj["relative_y1"],
                        obj["relative_x2"],
                        obj["relative_y2"],
                    ),
                    self._camera_resolution,
                )
                middle = ((x2 - x1) / 2) + x1
                if cv2.pointPolygonTest(self.coordinates, (middle, y2), False) >= 0:
                    self._objects_in_zone.append(obj)

    def on_connect(self, client):
        for device in self._mqtt_devices.values():
            device.on_connect(client)

    @property
    def coordinates(self):
        return self._coordinates

    @property
    def objects_in_zone(self):
        return self._objects_in_zone
