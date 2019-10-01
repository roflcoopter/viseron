# https://stackoverflow.com/questions/6198372/most-pythonic-way-to-provide-global-configuration-variables-in-config-py
# https://www.hackerearth.com/practice/notes/samarthbhargav/a-design-pattern-for-configuration-management-in-python/
# https://www.google.com/search?q=python+dynamic+amount+of+properties&rlz=1C1GCEA_enSE831SE831&oq=python+dynamic+amount+of+properties&aqs=chrome..69i57.5351j0j4&sourceid=chrome&ie=UTF-8
import json
import logging
from collections import namedtuple

import slugify as unicode_slug
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

LOGGER = logging.getLogger(__name__)

with open("/config/config.yaml", "r") as f:
    RAW_CONFIG = yaml.safe_load(f)


def slugify(text: str) -> str:
    """Slugify a given text."""
    return unicode_slug.slugify(text, separator="_")


def ensure_mqtt_name(camera_data: list) -> list:
    for camera in camera_data:
        if camera["mqtt_name"] is None:
            camera["mqtt_name"] = slugify(camera["name"])
    return camera_data


# TODO test this inside docker container
def ensure_label(data: list) -> list:
    for detector in data:
        if (
            detector["type"] in ["darknet", "edgetpu"]
            and detector["label_path"] is None
        ):
            raise Invalid(
                "Detector type {} requires a label file".format(detector["type"])
            )
        if detector["label_path"]:
            with open(detector["label_path"], "rt") as f:
                labels_file = f.read().rstrip("\n").split("\n")
            for label in detector["labels"]:
                if label not in labels_file:
                    raise Invalid("Provided label doesn't exist in label file")
    return data


def ensure_min_max(data: list) -> list:
    for detector in data:
        if detector["height_min"] > detector["height_max"]:
            raise Invalid("height_min may not be larger than height_max")
        if detector["width_min"] > detector["width_max"]:
            raise Invalid("width_min may not be larger than width_max")
    return data


def upper_case(data: dict) -> dict:
    data["level"] = data["level"].upper()
    return data


CAMERA_CONFIG = Schema(
    All(
        [
            {
                Required("name"): All(str, Length(min=1)),
                Required("mqtt_name", default=None): Any(All(str, Length(min=1)), None),
                Required("host"): All(str, Length(min=1)),
                Required("port", default=554): All(int, Range(min=1)),
                Optional("username", default=None): Any(All(str, Length(min=1)), None),
                Optional("password", default=None): Any(All(str, Length(min=1)), None),
                Required("path"): All(str, Length(min=1)),
                Optional("fps", default=None): Any(All(int, Range(min=1)), None),
            }
        ],
        ensure_mqtt_name,
    )
)

LABELS_CONFIG = Schema([str])

OBJECT_DETECTION_CONFIG = Schema(
    All(
        [
            {
                Required("type"): Any("darknet", "edgetpu", "posenet"),
                Required("model_path"): str,
                Required("label_path", default=None): Any(
                    All(str, Length(min=1)), None
                ),
                Required("model_width"): int,
                Required("model_height"): int,
                Required("threshold"): All(
                    Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
                ),
                Required("suppression"): All(
                    Any(0, 1, All(float, Range(min=0, max=1))), Coerce(float)
                ),
                Required("height_min"): int,
                Required("height_max"): int,
                Required("width_min"): int,
                Required("width_max"): int,
                Required("labels"): LABELS_CONFIG,
            }
        ],
        ensure_min_max,
        ensure_label,
    )
)

MOTION_DETECTION_DEFAULT = {
    "interval": 0,
    "trigger": False,
    "timeout": False,
    "width": 0,
    "height": 0,
    "area": 0,
    "frames": 0,
}

MOTION_DETECTION_CONFIG = Schema(
    {
        Required("interval"): int,
        Optional("trigger", default=True): bool,
        Optional("timeout", default=True): bool,
        Required("width"): int,
        Required("height"): int,
        Required("area"): int,
        Required("frames"): int,
    }
)

RECORDER_CONFIG = Schema(
    {
        Optional("lookback", default=10): All(int, Range(min=0)),
        Optional("timeout", default=10): All(int, Range(min=0)),
        Optional("retain", default=7): All(int, Range(min=1)),
        Optional("folder", default="/recordings"): str,
        Optional("extension", default="mp4"): str,
    }
)

MQTT_CONFIG = Schema(
    {
        Required("broker"): str,
        Required("port", default=1883): int,
        Optional("username", default=None): Any(str, None),
        Optional("password", default=None): Any(str, None),
        Optional("discovery_prefix", default="homeassistant"): str,
    }
)

LOGGING_CONFIG = Schema(
    All(
        upper_case,
        {
            Optional("level", default="INFO"): Any(
                "DEBUG", "INFO", "WARNING", "ERROR", "FATAL"
            )
        },
    )
)

VISERON_CONFIG = Schema(
    {
        Required("cameras"): CAMERA_CONFIG,
        Required("object_detection"): OBJECT_DETECTION_CONFIG,
        Optional(
            "motion_detection", default=MOTION_DETECTION_DEFAULT
        ): MOTION_DETECTION_CONFIG,
        Required("recorder", default={}): RECORDER_CONFIG,
        Required("mqtt"): MQTT_CONFIG,
        Required("logging", default={}): LOGGING_CONFIG,
    }
)

VALIDATED_CONFIG = VISERON_CONFIG(RAW_CONFIG)
# CONFIG = json.loads(
#    json.dumps(CONFIG),
#    object_hook=lambda d: namedtuple("ViseronConfig", d.keys())(*d.values()),
# )


class ViseronConfig:
    def __init__(self):
        self._config = json.loads(
            json.dumps(VALIDATED_CONFIG),
            object_hook=lambda d: namedtuple("ViseronConfig", d.keys())(*d.values()),
        )

    @property
    def config(self):
        return self._config
