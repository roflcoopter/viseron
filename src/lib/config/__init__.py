# https://stackoverflow.com/questions/6198372/most-pythonic-way-to-provide-global-configuration-variables-in-config-py
# https://www.hackerearth.com/practice/notes/samarthbhargav/a-design-pattern-for-configuration-management-in-python/
# https://www.google.com/search?q=python+dynamic+amount+of+properties&rlz=1C1GCEA_enSE831SE831&oq=python+dynamic+amount+of+properties&aqs=chrome..69i57.5351j0j4&sourceid=chrome&ie=UTF-8
import json
import logging
from collections import namedtuple

import yaml

from voluptuous import (
    All,
    Any,
    Coerce,
    Invalid,
    Length,
    Optional,
    Range,
    Required,
    Schema,
)

from .config_camera import CameraConfig
from .config_object_detection import ObjectDetectionConfig
from .config_motion_detection import MotionDetectionConfig
from .config_recorder import RecorderConfig
from .config_mqtt import MQTTConfig
from .config_logging import LoggingConfig

LOGGER = logging.getLogger(__name__)

with open("/config/config.yaml", "r") as config_file:
    RAW_CONFIG = yaml.safe_load(config_file)


# TODO test this inside docker container
def ensure_label(detector: dict) -> dict:
    if detector["type"] in ["darknet", "edgetpu"] and detector["label_path"] is None:
        raise Invalid("Detector type {} requires a label file".format(detector["type"]))
    if detector["label_path"]:
        with open(detector["label_path"], "rt") as label_file:
            labels_file = label_file.read().rstrip("\n").split("\n")
        for label in detector["labels"]:
            if label not in labels_file:
                raise Invalid("Provided label doesn't exist in label file")
    return detector


VISERON_CONFIG = Schema(
    {
        Required("cameras"): CameraConfig.schema,
        Required("object_detection"): ObjectDetectionConfig.schema,
        Optional(
            "motion_detection", default=MotionDetectionConfig.defaults
        ): MotionDetectionConfig.schema,
        Required("recorder", default={}): RecorderConfig.schema,
        Required("mqtt"): MQTTConfig.schema,
        Required("logging", default={}): LoggingConfig.schema,
    }
)

VALIDATED_CONFIG = VISERON_CONFIG(RAW_CONFIG)
CONFIG = json.loads(
    json.dumps(VALIDATED_CONFIG),
    object_hook=lambda d: namedtuple("ViseronConfig", d.keys())(*d.values()),
)


class ViseronConfig:
    config = CONFIG

    def __init__(self, camera=None):
        if camera:
            self._camera = CameraConfig(camera)

        self._cameras = self.config.cameras
        self._object_detection = ObjectDetectionConfig(self.config.object_detection)
        self._motion_detection = MotionDetectionConfig(self.config.motion_detection)
        self._recorder = RecorderConfig(self.config.recorder)
        self._mqtt = MQTTConfig(self.config.mqtt)
        self._logging = LoggingConfig(self.config.logging)

    @property
    def camera(self):
        return self._camera

    @property
    def cameras(self):
        return self._cameras

    @property
    def object_detection(self):
        return self._object_detection

    @property
    def motion_detection(self):
        return self._motion_detection

    @property
    def recorder(self):
        return self._recorder

    @property
    def mqtt(self):
        return self._mqtt

    @property
    def logging(self):
        return self._logging


def main():
    for camera in ViseronConfig.config.cameras:
        config = ViseronConfig(camera)
        print(config)


if __name__ == "__main__":
    main()
