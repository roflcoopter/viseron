import logging

import cv2

from const import TOPIC_FRAME_SCAN_POSTPROC
from lib.data_stream import DataStream
from lib.helpers import Filter, calculate_absolute_coords, report_labels
from lib.mqtt.binary_sensor import MQTTBinarySensor


class Zone:
    def __init__(self, zone, camera_resolution, config, mqtt_queue):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        if getattr(config.camera.logging, "level", None):
            self._logger.setLevel(config.camera.logging.level)

        self._coordinates = zone["coordinates"]
        self._camera_resolution = camera_resolution
        self._config = config
        self._mqtt_queue = mqtt_queue

        self._name = zone["name"]
        self._objects_in_zone = []
        self._labels_in_zone = []
        self._reported_label_count = {}
        self._object_filters = {}
        self._trigger_recorder = False
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

        self._post_processor_topic = (
            f"{config.camera.name_slug}/{TOPIC_FRAME_SCAN_POSTPROC}",
        )

    def filter_zone(self, frame):
        objects_in_zone = []
        labels_in_zone = []
        self._trigger_recorder = False
        for obj in frame.objects:
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

                    if self._object_filters[obj.label].triggers_recording:
                        self._trigger_recorder = True

                    if self._object_filters[obj.label].post_processor:
                        DataStream.publish_data(
                            (
                                f"{self._post_processor_topic}/"
                                f"{self._object_filters[obj.label].post_processor}"
                            ),
                            {
                                "camera_config": self._config,
                                "frame": frame,
                                "object": obj,
                                "zone": self._name,
                            },
                        )

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
    def objects_in_zone(self, objects):
        if objects == self._objects_in_zone:
            return

        self._objects_in_zone = objects
        if self._mqtt_queue:
            attributes = {}
            attributes["objects"] = [obj.formatted for obj in objects]
            self._mqtt_devices["zone"].publish(bool(objects), attributes)

    @property
    def labels_in_zone(self):
        return self._objects_in_zone

    @labels_in_zone.setter
    def labels_in_zone(self, labels):
        self._labels_in_zone, self._reported_label_count = report_labels(
            labels,
            self._labels_in_zone,
            self._reported_label_count,
            self._mqtt_queue,
            self._mqtt_devices,
        )

    @property
    def trigger_recorder(self):
        return self._trigger_recorder

    @property
    def name(self):
        return self._name
