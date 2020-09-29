# https://stackoverflow.com/questions/6198372/most-pythonic-way-to-provide-global-configuration-variables-in-config-py
# https://www.hackerearth.com/practice/notes/samarthbhargav/a-design-pattern-for-configuration-management-in-python/
# https://www.google.com/search?q=python+dynamic+amount+of+properties&rlz=1C1GCEA_enSE831SE831&oq=python+dynamic+amount+of+properties&aqs=chrome..69i57.5351j0j4&sourceid=chrome&ie=UTF-8
import json
import os
import sys
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

from const import (
    CONFIG_PATH,
    DEFAULT_CONFIG,
    ENV_CUDA_SUPPORTED,
    ENV_OPENCL_SUPPORTED,
    ENV_RASPBERRYPI3,
    SECRETS_PATH,
)

from .config_camera import CameraConfig
from .config_logging import LoggingConfig
from .config_motion_detection import MotionDetectionConfig
from .config_mqtt import MQTTConfig
from .config_object_detection import ObjectDetectionConfig
from .config_post_processors import PostProcessorConfig
from .config_recorder import RecorderConfig


def create_default_config():
    try:
        with open(CONFIG_PATH, "wt") as config_file:
            config_file.write(DEFAULT_CONFIG)
    except OSError:
        print("Unable to create default configuration file", CONFIG_PATH)
        return False
    return True


def load_secrets():
    try:
        with open(SECRETS_PATH, "r") as secrets_file:
            return yaml.load(secrets_file, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        return None


def load_config():
    secrets = load_secrets()

    def secret_yaml(_, node):
        if secrets is None:
            raise ValueError(
                "!secret found in config.yaml, but no secrets.yaml exists. "
                f"Make sure it exists under {SECRETS_PATH}"
            )
        if node.value not in secrets:
            raise ValueError(f"secret {node.value} does not exist in secrets.yaml")
        return secrets[node.value]

    yaml.add_constructor("!secret", secret_yaml, Loader=yaml.SafeLoader)

    try:
        with open(CONFIG_PATH, "r") as config_file:
            return yaml.load(config_file, Loader=yaml.SafeLoader)
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
        Optional("object_detection", default={}): ObjectDetectionConfig.schema,
        Optional(
            "motion_detection", default=MotionDetectionConfig.defaults
        ): MotionDetectionConfig.schema,
        Optional("post_processors", default={}): PostProcessorConfig.schema,
        Optional("recorder", default={}): RecorderConfig.schema,
        Optional("mqtt", default=None): Any(MQTTConfig.schema, None),
        Optional("logging", default={}): LoggingConfig.schema,
    }
)

raw_config = load_config()

CONFIG = VISERON_CONFIG_SCHEMA(raw_config)


class BaseConfig:
    def __init__(self):
        self._object_detection = None
        self._motion_detection = None
        self._post_processors = None
        self._recorder = None
        self._mqtt = None
        self._logging = None

    @property
    def object_detection(self):
        return self._object_detection

    @property
    def motion_detection(self):
        return self._motion_detection

    @property
    def post_processors(self):
        return self._post_processors

    @property
    def recorder(self):
        return self._recorder

    @property
    def mqtt(self):
        return self._mqtt

    @property
    def logging(self):
        return self._logging


class ViseronConfig(BaseConfig):
    def __init__(self, config):
        super().__init__()
        self._cameras = config["cameras"]
        self._object_detection = config["object_detection"]
        self._motion_detection = config["motion_detection"]
        self._post_processors = PostProcessorConfig(config["post_processors"])
        self._recorder = RecorderConfig(config["recorder"])
        self._mqtt = MQTTConfig(config["mqtt"]) if config.get("mqtt", None) else None
        self._logging = LoggingConfig(config["logging"])

    @property
    def cameras(self):
        return self._cameras


class NVRConfig(BaseConfig):
    def __init__(
        self, camera, object_detection, motion_detection, recorder, mqtt, logging
    ):
        super().__init__()
        self._camera = CameraConfig(camera)
        self._object_detection = ObjectDetectionConfig(
            object_detection, self._camera.object_detection, self._camera.zones
        )
        self._motion_detection = MotionDetectionConfig(
            motion_detection, self._camera.motion_detection,
        )
        self._recorder = recorder
        self._mqtt = mqtt
        self._logging = logging

    @property
    def camera(self):
        return self._camera
