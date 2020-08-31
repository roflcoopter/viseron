# https://stackoverflow.com/questions/6198372/most-pythonic-way-to-provide-global-configuration-variables-in-config-py
# https://www.hackerearth.com/practice/notes/samarthbhargav/a-design-pattern-for-configuration-management-in-python/
# https://www.google.com/search?q=python+dynamic+amount+of+properties&rlz=1C1GCEA_enSE831SE831&oq=python+dynamic+amount+of+properties&aqs=chrome..69i57.5351j0j4&sourceid=chrome&ie=UTF-8
import json
import logging
import os
import sys
from collections import namedtuple

import yaml

from const import (
    CONFIG_PATH,
    DEFAULT_CONFIG,
    DARKNET_DEFAULTS,
    EDGETPU_DEFAULTS,
    ENV_CUDA_SUPPORTED,
    ENV_OPENCL_SUPPORTED,
    ENV_RASPBERRYPI3,
)
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
from .config_logging import LoggingConfig
from .config_motion_detection import MotionDetectionConfig
from .config_mqtt import MQTTConfig
from .config_object_detection import ObjectDetectionConfig
from .config_recorder import RecorderConfig

LOGGER = logging.getLogger(__name__)


def get_object_detection_defaults():
    if (
        os.getenv(ENV_OPENCL_SUPPORTED) == "true"
        or os.getenv(ENV_CUDA_SUPPORTED) == "true"
    ):
        return DARKNET_DEFAULTS
    if os.getenv(ENV_RASPBERRYPI3) == "true":
        return EDGETPU_DEFAULTS

    return DARKNET_DEFAULTS


def create_default_config():
    try:
        with open(CONFIG_PATH, "wt") as config_file:
            config_file.write(DEFAULT_CONFIG)
    except OSError:
        print("Unable to create default configuration file", CONFIG_PATH)
        return False
    return True


def load_config():
    try:
        with open(CONFIG_PATH, "r") as config_file:
            return yaml.safe_load(config_file)
    except FileNotFoundError:
        print(
            f"Unable to find configuration. Creating default one in {CONFIG_PATH}\n"
            f"Please fill in the necessary configuration options and restart Viseron"
        )
        create_default_config()
        sys.exit()


VISERON_CONFIG_SCHEMA = Schema(
    {
        Required("cameras"): CameraConfig.schema,
        Optional(
            "object_detection", default=get_object_detection_defaults()
        ): ObjectDetectionConfig.schema,
        Optional(
            "motion_detection", default=MotionDetectionConfig.defaults
        ): MotionDetectionConfig.schema,
        Optional("recorder", default={}): RecorderConfig.schema,
        Optional("mqtt", default=None): Any(MQTTConfig.schema, None),
        Optional("logging", default={}): LoggingConfig.schema,
    }
)

raw_config = load_config()

VALIDATED_CONFIG = VISERON_CONFIG_SCHEMA(raw_config)
CONFIG = json.loads(
    json.dumps(VALIDATED_CONFIG),
    object_hook=lambda d: namedtuple("ViseronConfig", d.keys())(*d.values()),
)


class ViseronConfig:
    config = CONFIG

    def __init__(self, camera=None):
        self._camera = CameraConfig(camera) if camera else None
        LOGGER.error(
            f"CAMERA {getattr(self._camera, 'motion_detection', None) if self._camera else None}"
        )

        self._cameras = self.config.cameras
        self._object_detection = ObjectDetectionConfig(self.config.object_detection)
        self._motion_detection = MotionDetectionConfig(
            self.config.motion_detection,
            getattr(self._camera, "motion_detection", None) if self._camera else None,
        )
        self._recorder = RecorderConfig(self.config.recorder)
        self._mqtt = MQTTConfig(self.config.mqtt) if self.config.mqtt else None
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
