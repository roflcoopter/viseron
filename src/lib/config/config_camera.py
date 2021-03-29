import logging
import os
import re
from typing import Dict, List

import numpy as np
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
    CAMERA_GLOBAL_ARGS,
    CAMERA_HWACCEL_ARGS,
    CAMERA_INPUT_ARGS,
    CAMERA_OUTPUT_ARGS,
    ENV_CUDA_SUPPORTED,
    ENV_RASPBERRYPI3,
    ENV_VAAPI_SUPPORTED,
    FFMPEG_RECOVERABLE_ERRORS,
    HWACCEL_CUDA_DECODER_CODEC_MAP,
    HWACCEL_RPI3_DECODER_CODEC_MAP,
    HWACCEL_VAAPI,
)
from lib.helpers import slugify

from .config_logging import SCHEMA as LOGGING_SCHEMA
from .config_logging import LoggingConfig
from .config_object_detection import LABELS_SCHEMA, LabelConfig

LOGGER = logging.getLogger(__name__)

MQTT_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\.]+$")


def ensure_mqtt_name(camera: Dict[str, str]) -> Dict[str, str]:
    if camera["mqtt_name"] is None:
        camera["mqtt_name"] = slugify(camera["name"])

    match = MQTT_NAME_REGEX.match(camera["mqtt_name"])

    if not match:
        raise Invalid(
            f"Error in config for camera {camera['name']}. "
            f"mqtt_name can only contain the characters [a-zA-Z0-9_], "
            f"got {camera['mqtt_name']}"
        )

    return camera


def check_for_hwaccels(hwaccel_args: List[str]) -> List[str]:
    if hwaccel_args:
        return hwaccel_args

    # Dont enable VA-API if CUDA is available
    if (
        os.getenv(ENV_VAAPI_SUPPORTED) == "true"
        and os.getenv(ENV_CUDA_SUPPORTED) != "true"
    ):
        return HWACCEL_VAAPI
    return hwaccel_args


STREAM_SCEHMA = Schema(
    {
        Required("path"): All(str, Length(min=1)),
        Optional("width", default=None): Any(int, None),
        Optional("height", default=None): Any(int, None),
        Optional("fps", default=None): Any(All(int, Range(min=1)), None),
        Optional("input_args", default=CAMERA_INPUT_ARGS): list,
        Optional("hwaccel_args", default=CAMERA_HWACCEL_ARGS): check_for_hwaccels,
        Optional("codec", default=""): str,
        Optional("rtsp_transport", default="tcp"): Any(
            "tcp", "udp", "udp_multicast", "http"
        ),
        Optional("filter_args", default=[]): list,
    }
)

CAMERA_SCHEMA = STREAM_SCEHMA.extend(
    {
        Required("name"): All(str, Length(min=1)),
        Optional("mqtt_name", default=None): Any(All(str, Length(min=1)), None),
        Required("stream_format", default="rtsp"): Any("rtsp", "mjpeg"),
        Required("host"): All(str, Length(min=1)),
        Required("port"): All(int, Range(min=1)),
        Optional("username", default=None): Any(All(str, Length(min=1)), None),
        Optional("password", default=None): Any(All(str, Length(min=1)), None),
        Optional("global_args", default=CAMERA_GLOBAL_ARGS): list,
        Optional("substream"): STREAM_SCEHMA,
        Optional("motion_detection"): Any(
            {
                Optional("interval"): Any(int, float),
                Optional("trigger_detector"): bool,
                Optional("timeout"): bool,
                Optional("max_timeout"): int,
                Optional("width"): int,
                Optional("height"): int,
                Optional("area"): All(
                    Any(All(float, Range(min=0.0, max=1.0)), 1, 0), Coerce(float),
                ),
                Optional("threshold"): All(int, Range(min=0, max=255)),
                Optional("alpha"): All(
                    Any(All(float, Range(min=0.0, max=1.0)), 1, 0), Coerce(float),
                ),
                Optional("frames"): int,
                Optional("mask", default=[]): [
                    {Required("points"): [{Required("x"): int, Required("y"): int,}],}
                ],
                Optional("logging"): LOGGING_SCHEMA,
            },
            None,
        ),
        Optional("object_detection"): Any(
            {
                Optional("interval"): Any(int, float),
                Optional("labels"): LABELS_SCHEMA,
                Optional("logging"): LOGGING_SCHEMA,
                Optional("log_all_objects"): bool,
            },
            None,
        ),
        Optional("zones", default=[]): [
            {
                Required("name"): str,
                Required("points"): [{Required("x"): int, Required("y"): int,}],
                Optional("labels"): LABELS_SCHEMA,
            }
        ],
        Optional("publish_image", default=False): Any(True, False),
        Optional("ffmpeg_loglevel", default="fatal"): Any(
            "quiet",
            "panic",
            "fatal",
            "error",
            "warning",
            "info",
            "verbose",
            "debug",
            "trace",
        ),
        Optional("ffmpeg_recoverable_errors", default=FFMPEG_RECOVERABLE_ERRORS): [str],
        Optional("logging"): LOGGING_SCHEMA,
    },
)

SCHEMA = Schema(All([All(CAMERA_SCHEMA, ensure_mqtt_name,)],))


class Stream:
    def __init__(self, camera):
        self._host = camera["host"]
        self._port = camera["port"]
        self._username = camera["username"]
        self._password = camera["password"]
        self._path = camera["path"]
        self._width = camera["width"]
        self._height = camera["height"]
        self._fps = camera["fps"]
        self._stream_format = camera["stream_format"]
        self._input_args = camera["input_args"]
        self._hwaccel_args = camera["hwaccel_args"]
        self._codec = camera["codec"]
        self._rtsp_transport = camera["rtsp_transport"]

    def get_codec_map(self):
        if self.stream_format == "rtsp":
            if os.getenv(ENV_CUDA_SUPPORTED) == "true":
                return HWACCEL_CUDA_DECODER_CODEC_MAP
            if os.getenv(ENV_RASPBERRYPI3) == "true":
                return HWACCEL_RPI3_DECODER_CODEC_MAP
        return {}

    @property
    def stream_format(self):
        return self._stream_format

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
    def input_args(self):
        return self._input_args

    @property
    def hwaccel_args(self):
        return self._hwaccel_args

    @property
    def codec(self):
        return ["-c:v", self._codec] if self._codec else []

    @property
    def codec_map(self):
        return self.get_codec_map()

    @property
    def rtsp_transport(self):
        return self._rtsp_transport

    @property
    def protocol(self):
        return "rtsp" if self.stream_format == "rtsp" else "http"

    @property
    def stream_url(self):
        if self.username and self.password:
            return (
                f"{self.protocol}://{self.username}:{self.password}@"
                f"{self.host}:{self.port}{self.path}"
            )
        return f"{self.protocol}://{self.host}:{self.port}{self.path}"


class Substream(Stream):
    def __init__(self, camera):
        super().__init__(camera)
        self._path = camera["substream"]["path"]
        self._width = camera["substream"]["width"]
        self._height = camera["substream"]["height"]
        self._fps = camera["substream"]["fps"]
        self._input_args = camera["substream"]["input_args"]
        self._hwaccel_args = camera["substream"]["hwaccel_args"]
        self._codec = camera["substream"]["codec"]
        self._rtsp_transport = camera["substream"]["rtsp_transport"]


class CameraConfig(Stream):
    schema = SCHEMA

    def __init__(self, camera):
        super().__init__(camera)
        self._name = camera["name"]
        self._name_slug = slugify(self.name)
        self._mqtt_name = camera["mqtt_name"]
        self._global_args = camera["global_args"]
        self._filter_args = camera["filter_args"]
        self._substream = None
        if camera.get("substream", None):
            self._substream = Substream(camera)
        self._motion_detection = camera.get("motion_detection", {})
        self._object_detection = camera.get("object_detection", {})
        self._zones = self.generate_zones(camera["zones"])
        self._publish_image = camera["publish_image"]
        self._ffmpeg_loglevel = camera["ffmpeg_loglevel"]
        self._ffmpeg_recoverable_errors = camera["ffmpeg_recoverable_errors"]
        self._logging = None
        if camera.get("logging", None):
            self._logging = LoggingConfig(camera["logging"])

    def generate_zones(self, zones):
        zone_list = []
        for zone in zones:
            zone_dict = {}
            zone_dict["name"] = zone["name"]

            zone_labels = zone.get("labels", [])
            if not zone_labels:
                zone_labels = self.object_detection.get("labels", [])
            labels = []
            for label in zone_labels:
                labels.append(LabelConfig(label))
            zone_dict["labels"] = labels

            point_list = []
            for point in zone["points"]:
                point_list.append([point["x"], point["y"]])
            zone_dict["coordinates"] = np.array(point_list)
            zone_list.append(zone_dict)

        return zone_list

    @property
    def name(self):
        return self._name

    @property
    def name_slug(self):
        return self._name_slug

    @property
    def mqtt_name(self):
        return self._mqtt_name

    @property
    def global_args(self):
        return self._global_args

    @property
    def filter_args(self):
        return self._filter_args

    @property
    def output_args(self):
        return CAMERA_OUTPUT_ARGS

    @property
    def substream(self):
        return self._substream

    @property
    def motion_detection(self):
        return self._motion_detection

    @property
    def object_detection(self):
        return self._object_detection

    @property
    def zones(self):
        return self._zones

    @property
    def publish_image(self):
        return self._publish_image

    @property
    def ffmpeg_loglevel(self):
        return self._ffmpeg_loglevel

    @property
    def ffmpeg_recoverable_errors(self):
        return self._ffmpeg_recoverable_errors

    @property
    def logging(self):
        return self._logging
