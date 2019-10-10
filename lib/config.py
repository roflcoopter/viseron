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
# with open("/workspace/viseron/config/config.yaml", "r") as f:
#    RAW_CONFIG = yaml.safe_load(f)


def slugify(text: str) -> str:
    """Slugify a given text."""
    return unicode_slug.slugify(text, separator="_")


def ensure_mqtt_name(camera_data: list) -> list:
    for camera in camera_data:
        if camera["mqtt_name"] is None:
            camera["mqtt_name"] = slugify(camera["name"])
    return camera_data


# TODO test this inside docker container
def ensure_label(detector: dict) -> dict:
    if detector["type"] in ["darknet", "edgetpu"] and detector["label_path"] is None:
        raise Invalid("Detector type {} requires a label file".format(detector["type"]))
    if detector["label_path"]:
        with open(detector["label_path"], "rt") as f:
            labels_file = f.read().rstrip("\n").split("\n")
        for label in detector["labels"]:
            if label not in labels_file:
                raise Invalid("Provided label doesn't exist in label file")
    return detector


def ensure_min_max(detector: dict) -> dict:
    if detector["height_min"] > detector["height_max"]:
        raise Invalid("height_min may not be larger than height_max")
    if detector["width_min"] > detector["width_max"]:
        raise Invalid("width_min may not be larger than width_max")
    return detector


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
                Optional("width", default=None): Any(int, None),
                Optional("height", default=None): Any(int, None),
                Optional("fps", default=None): Any(All(int, Range(min=1)), None),
            }
        ],
        ensure_mqtt_name,
    )
)

LABELS_CONFIG = Schema([str])

OBJECT_DETECTION_CONFIG = Schema(
    All(
        {
            Required("type"): Any("darknet", "edgetpu", "posenet"),
            Required("model_path"): str,
            Required("model_config", default=None): Any(str, None),
            Required("label_path", default=None): Any(All(str, Length(min=1)), None),
            Required("model_width"): int,
            Required("model_height"): int,
            Required("interval", default=1): int,
            Required("threshold"): All(
                Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
            ),
            Required("suppression"): All(
                Any(0, 1, All(float, Range(min=0, max=1))), Coerce(float)
            ),
            Required("height_min"): float,
            Required("height_max"): float,
            Required("width_min"): float,
            Required("width_max"): float,
            Required("labels"): LABELS_CONFIG,
        },
        ensure_min_max,
        # TODO ADD THIS BACK
        # ensure_label,
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
CONFIG = json.loads(
    json.dumps(VALIDATED_CONFIG),
    object_hook=lambda d: namedtuple("ViseronConfig", d.keys())(*d.values()),
)


class CameraConfig:
    def __init__(self, camera):
        self._name = camera.name
        self._mqtt_name = camera.mqtt_name
        self._host = camera.host
        self._port = camera.port
        self._username = camera.username
        self._password = camera.password
        self._path = camera.path
        self._width = camera.width
        self._height = camera.height
        self._fps = camera.fps

    @property
    def name(self):
        return self._name

    @property
    def mqtt_name(self):
        return self._mqtt_name

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def username(self):
        return self._username

    @property
    def password(self):
        return self._password

    @property
    def path(self):
        return self._path

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def fps(self):
        return self._fps

    @property
    def stream_url(self):
        return (
            f"rtsp://{self.username}:{self.password}@{self.host}:{self.port}{self.path}"
        )


class ObjectDetectionConfig:
    def __init__(self, object_detection):
        self._type = object_detection.type
        self._model_path = object_detection.model_path
        self._label_path = object_detection.label_path
        self._model_width = object_detection.model_width
        self._model_height = object_detection.model_height
        self._interval = object_detection.interval
        self._threshold = object_detection.threshold
        self._suppression = object_detection.suppression
        self._height_min = object_detection.height_min
        self._height_max = object_detection.height_max
        self._width_min = object_detection.width_min
        self._width_max = object_detection.width_max
        self._labels = object_detection.labels

    @property
    def type(self):
        return self._type

    @property
    def model_path(self):
        return self._model_path

    @property
    def label_path(self):
        return self._label_path

    @property
    def model_width(self):
        return self._model_width

    @property
    def model_height(self):
        return self._model_height

    @property
    def interval(self):
        return self._interval

    @property
    def threshold(self):
        return self._threshold

    @property
    def suppression(self):
        return self._suppression

    @property
    def height_min(self):
        return self._height_min

    @property
    def height_max(self):
        return self._height_max

    @property
    def width_min(self):
        return self._width_min

    @property
    def width_max(self):
        return self._width_max

    @property
    def labels(self):
        return self._labels


class MotionDetectionConfig:
    def __init__(self, motion_detection):
        self._interval = motion_detection.interval
        self._trigger = motion_detection.trigger
        self._timeout = motion_detection.timeout
        self._width = motion_detection.width
        self._height = motion_detection.height
        self._area = motion_detection.area
        self._frames = motion_detection.frames

    @property
    def interval(self):
        return self._interval

    @property
    def trigger(self):
        return self._trigger

    @property
    def timeout(self):
        return self._timeout

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def area(self):
        return self._area

    @property
    def frames(self):
        return self._frames


class RecorderConfig:
    def __init__(self, recorder):
        self._lookback = recorder.lookback
        self._timeout = recorder.timeout
        self._retain = recorder.retain
        self._folder = recorder.folder
        self._extension = recorder.extension

    @property
    def lookback(self):
        return self._lookback

    @property
    def timeout(self):
        return self._timeout

    @property
    def retain(self):
        return self._retain

    @property
    def folder(self):
        return self._folder

    @property
    def extension(self):
        return self._extension


class ViseronConfig:
    config = CONFIG

    def __init__(self, camera):
        self._camera = CameraConfig(camera)
        self._object_detection = ObjectDetectionConfig(self.config.object_detection)
        self._motion_detection = MotionDetectionConfig(self.config.motion_detection)
        self._recorder = RecorderConfig(self.config.recorder)

    @property
    def camera(self):
        return self._camera

    @property
    def object_detection(self):
        return self._object_detection

    @property
    def motion_detection(self):
        return self._motion_detection

    @property
    def recorder(self):
        return self._recorder


def main():
    for camera in ViseronConfig.config.cameras:
        config = ViseronConfig(camera)
        print(config.camera.stream_url)
        print(config.object_detection.labels)
        print(config.motion_detection.timeout)
        print(config.recorder.folder)


if __name__ == "__main__":
    main()
