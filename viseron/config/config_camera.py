"""Camera config."""
import logging
import os
import re
from typing import Dict, List

from voluptuous import (
    All,
    Any,
    Coerce,
    Invalid,
    Length,
    Maybe,
    Optional,
    Range,
    Required,
    Schema,
)

import viseron.config
from viseron.const import (
    CAMERA_GLOBAL_ARGS,
    CAMERA_HWACCEL_ARGS,
    CAMERA_INPUT_ARGS,
    ENV_CUDA_SUPPORTED,
    ENV_JETSON_NANO,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
    ENV_VAAPI_SUPPORTED,
    FFMPEG_RECOVERABLE_ERRORS,
    HWACCEL_CUDA_DECODER_CODEC_MAP,
    HWACCEL_JETSON_NANO_DECODER_CODEC_MAP,
    HWACCEL_RPI3_DECODER_CODEC_MAP,
    HWACCEL_RPI4_DECODER_CODEC_MAP,
    HWACCEL_VAAPI,
)
from viseron.helpers import generate_numpy_from_coordinates, slugify

from .config_logging import SCHEMA as LOGGING_SCHEMA, LoggingConfig
from .config_object_detection import LABELS_SCHEMA, LabelConfig

LOGGER = logging.getLogger(__name__)

MQTT_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\.]+$")
SLUG_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]+$")

STREAM_FORMAT_MAP = {
    "rtsp": {"protocol": "rtsp", "timeout_option": ["-stimeout", "5000000"]},
    "rtmp": {"protocol": "rtmp", "timeout_option": ["-rw_timeout", "5000000"]},
    "mjpeg": {"protocol": "http", "timeout_option": ["-stimeout", "5000000"]},
}


def ensure_slug(value: str) -> str:
    """Validate an string to only consist of certain characters."""
    regex = re.compile(SLUG_REGEX)
    if not regex.match(value):
        raise Invalid("Invalid string")
    return value


def ensure_mqtt_name(camera: Dict[str, str]) -> Dict[str, str]:
    """Ensure name is compatible with MQTT."""
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
    """Return hardware acceleration args for FFmpeg."""
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
        Required("stream_format", default="rtsp"): Any("rtsp", "rtmp", "mjpeg"),
        Required("path"): All(str, Length(min=1)),
        Required("port"): All(int, Range(min=1)),
        Optional("width", default=None): Maybe(int),
        Optional("height", default=None): Maybe(int),
        Optional("fps", default=None): Maybe(All(int, Range(min=1))),
        Optional("input_args", default=None): Maybe(list),
        Optional("hwaccel_args", default=CAMERA_HWACCEL_ARGS): check_for_hwaccels,
        Optional("codec", default=""): str,
        Optional("audio_codec", default="unset"): Maybe(str),
        Optional("rtsp_transport", default="tcp"): Any(
            "tcp", "udp", "udp_multicast", "http"
        ),
        Optional("filter_args", default=[]): list,
        Optional("pix_fmt", default="nv12"): Any("nv12", "yuv420p"),
        Optional("frame_timeout", default=60): int,
    }
)

MJPEG_STREAM_SCHEMA = Schema(
    {
        Optional("width", default=0): All(Any(int, str), Coerce(int)),
        Optional("height", default=0): All(Any(int, str), Coerce(int)),
        Optional("draw_objects", default=False): Any(str, bool, bytes),
        Optional("draw_motion", default=False): Any(str, bool, bytes),
        Optional("draw_motion_mask", default=False): Any(str, bool, bytes),
        Optional("draw_object_mask", default=False): Any(str, bool, bytes),
        Optional("draw_zones", default=False): Any(str, bool, bytes),
        Optional("rotate", default=0): All(Any(int, str), Coerce(int)),
        Optional("mirror", default=False): Any(str, bool, bytes),
    }
)

CAMERA_SCHEMA = STREAM_SCEHMA.extend(
    {
        Required("name"): All(str, Length(min=1)),
        Optional("mqtt_name", default=None): Maybe(All(str, Length(min=1))),
        Required("host"): All(str, Length(min=1)),
        Optional("username", default=None): Maybe(All(str, Length(min=1))),
        Optional("password", default=None): Maybe(All(str, Length(min=1))),
        Optional("global_args", default=CAMERA_GLOBAL_ARGS): list,
        Optional("substream"): STREAM_SCEHMA,
        # Optional("motion_detection"):
        Optional("object_detection"): Maybe(
            {
                Optional("enable"): bool,
                Optional("fps"): All(Any(float, int), Coerce(float), Range(min=0.0)),
                Optional("labels"): LABELS_SCHEMA,
                Optional("mask", default=[]): [
                    {
                        Required("points"): [
                            {
                                Required("x"): int,
                                Required("y"): int,
                            }
                        ],
                    }
                ],
                Optional("max_frame_age"): All(
                    Any(float, int), Coerce(float), Range(min=0.0)
                ),
                Optional("logging"): LOGGING_SCHEMA,
                Optional("log_all_objects"): bool,
            },
        ),
        Optional("zones", default=[]): [
            {
                Required("name"): str,
                Required("points"): [
                    {
                        Required("x"): int,
                        Required("y"): int,
                    }
                ],
                Optional("labels"): LABELS_SCHEMA,
            }
        ],
        Optional("publish_image", default=False): bool,
        Optional("ffmpeg_loglevel", default="error"): Any(
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
        Optional("ffprobe_loglevel", default="error"): Any(
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
        Optional("static_mjpeg_streams", default={}): {
            All(str, ensure_slug): MJPEG_STREAM_SCHEMA
        },
        Optional("logging"): LOGGING_SCHEMA,
    },
)


class Stream:
    """Stream config."""

    def __init__(self, camera):
        self._stream_format = camera["stream_format"]
        self._host = camera["host"]
        self._port = camera["port"]
        self._username = camera["username"]
        self._password = camera["password"]
        self._path = camera["path"]
        self._width = camera["width"]
        self._height = camera["height"]
        self._fps = camera["fps"]
        self._input_args = camera["input_args"]
        self._hwaccel_args = camera["hwaccel_args"]
        self._codec = camera["codec"]
        self._audio_codec = camera["audio_codec"]
        self._rtsp_transport = camera["rtsp_transport"]
        self._filter_args = camera["filter_args"]
        self._pix_fmt = camera["pix_fmt"]
        self._frame_timeout = camera["frame_timeout"]

    def get_codec_map(self):
        """Return codec for specific hardware."""
        if self.stream_format in ["rtsp", "rtmp"]:
            if os.getenv(ENV_RASPBERRYPI3) == "true":
                return HWACCEL_RPI3_DECODER_CODEC_MAP
            if os.getenv(ENV_RASPBERRYPI4) == "true":
                return HWACCEL_RPI4_DECODER_CODEC_MAP
            if os.getenv(ENV_JETSON_NANO) == "true":
                return HWACCEL_JETSON_NANO_DECODER_CODEC_MAP
            if os.getenv(ENV_CUDA_SUPPORTED) == "true":
                return HWACCEL_CUDA_DECODER_CODEC_MAP
        return {}

    @property
    def stream_format(self):
        """Return stream format."""
        return self._stream_format

    @property
    def host(self):
        """Return host."""
        return self._host

    @property
    def port(self):
        """Return port."""
        return self._port

    @property
    def username(self):
        """Return username."""
        return self._username

    @property
    def password(self):
        """Return password."""
        return self._password

    @property
    def path(self):
        """Return path."""
        return self._path

    @property
    def width(self):
        """Return width."""
        return self._width

    @property
    def height(self):
        """Return height."""
        return self._height

    @property
    def fps(self):
        """Return fps."""
        return self._fps

    @property
    def input_args(self):
        """Return input_args."""
        if self._input_args:
            return self._input_args
        return CAMERA_INPUT_ARGS + self.timeout_option

    @property
    def hwaccel_args(self):
        """Return hwaccel_args."""
        return self._hwaccel_args

    @property
    def codec(self):
        """Return codec for FFmpeg command."""
        return ["-c:v", self._codec] if self._codec else []

    @property
    def codec_map(self):
        """Return predefined codec map."""
        return self.get_codec_map()

    @property
    def audio_codec(self):
        """Return audio_codec for FFmpeg command."""
        return self._audio_codec

    @property
    def rtsp_transport(self):
        """Return RTSP transport."""
        return self._rtsp_transport

    @property
    def filter_args(self):
        """Return FFmpeg filter args."""
        return self._filter_args

    @property
    def frame_timeout(self):
        """Return frame timeout."""
        return self._frame_timeout

    @property
    def pix_fmt(self):
        """Return FFmpeg pix fmt."""
        return self._pix_fmt

    @property
    def protocol(self):
        """Return protocol."""
        return STREAM_FORMAT_MAP[self.stream_format]["protocol"]

    @property
    def timeout_option(self):
        """Return timeout option."""
        return STREAM_FORMAT_MAP[self.stream_format]["timeout_option"]

    @property
    def stream_url(self):
        """Return stream url."""
        if self.username and self.password:
            return (
                f"{self.protocol}://{self.username}:{self.password}@"
                f"{self.host}:{self.port}{self.path}"
            )
        return f"{self.protocol}://{self.host}:{self.port}{self.path}"


class Substream(Stream):
    """Substream config."""

    def __init__(self, camera):
        super().__init__(camera)
        self._stream_format = camera["substream"]["stream_format"]
        self._port = camera["substream"]["port"]
        self._path = camera["substream"]["path"]
        self._width = camera["substream"]["width"]
        self._height = camera["substream"]["height"]
        self._fps = camera["substream"]["fps"]
        self._input_args = camera["substream"]["input_args"]
        self._hwaccel_args = camera["substream"]["hwaccel_args"]
        self._codec = camera["substream"]["codec"]
        self._rtsp_transport = camera["substream"]["rtsp_transport"]
        self._filter_args = camera["substream"]["filter_args"]


class CameraConfig(Stream):
    """Camera config."""

    def __init__(self, camera, motion_detection):
        # Inherit values from global motion detection config
        if not camera.get("motion_detection"):
            camera["motion_detection"] = {}

        camera["motion_detection"]["type"] = motion_detection["type"]
        local_motion_detection_config = motion_detection.copy()
        local_motion_detection_config.update(camera["motion_detection"])
        camera["motion_detection"] = local_motion_detection_config

        self._schema = self.build_schema(camera)

        self._validated_config = self._schema(camera)

        super().__init__(self._validated_config)
        self._name = self._validated_config["name"]
        self._name_slug = slugify(self.name)
        self._mqtt_name = self._validated_config["mqtt_name"]
        self._global_args = self._validated_config["global_args"]
        self._substream = None
        if self._validated_config.get("substream", None):
            self._substream = Substream(self._validated_config)
        self._motion_detection = self._validated_config.get("motion_detection", {})
        self._object_detection = self._validated_config.get("object_detection", {})
        self._zones = self.generate_zones(self._validated_config["zones"])
        self._publish_image = self._validated_config["publish_image"]
        self._ffmpeg_loglevel = self._validated_config["ffmpeg_loglevel"]
        self._ffmpeg_recoverable_errors = self._validated_config[
            "ffmpeg_recoverable_errors"
        ]
        self._ffprobe_loglevel = self._validated_config["ffprobe_loglevel"]
        self._static_mjpeg_streams = self._validated_config["static_mjpeg_streams"]
        self._logging = None
        if self._validated_config.get("logging", None):
            self._logging = LoggingConfig(self._validated_config["logging"])

    @staticmethod
    def build_schema(camera):
        """Build dynamic schema.

        This is needed because the motion detection schema is loaded dynamically
        so it cannot be hardcoded.
        """
        _, schema = viseron.config.import_motion_detection(camera["motion_detection"])
        camera_schema = CAMERA_SCHEMA.extend(
            {
                Optional("motion_detection"): schema,
            }
        )
        schema = Schema(
            All(
                camera_schema,
                ensure_mqtt_name,
            )
        )
        return schema

    def generate_zones(self, zones):
        """Return a list of zones converted to numpy arrays."""
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

            zone_dict["coordinates"] = generate_numpy_from_coordinates(zone["points"])
            zone_list.append(zone_dict)

        return zone_list

    @property
    def validated_config(self):
        """Return raw validated config."""
        return self._validated_config

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def name_slug(self):
        """Return name in slug format."""
        return self._name_slug

    @property
    def mqtt_name(self):
        """Return MQTT name."""
        return self._mqtt_name

    @property
    def global_args(self):
        """Return FFmpeg global args."""
        return self._global_args

    @property
    def output_args(self):
        """Return FFmpeg output args."""
        return ["-f", "rawvideo", "-pix_fmt", self.pix_fmt, "pipe:1"]

    @property
    def substream(self):
        """Return substream config."""
        return self._substream

    @property
    def motion_detection(self):
        """Return motion detection config."""
        return self._motion_detection

    @property
    def object_detection(self):
        """Return object detection config."""
        return self._object_detection

    @property
    def zones(self):
        """Return zones."""
        return self._zones

    @property
    def publish_image(self):
        """Return publish_image."""
        return self._publish_image

    @property
    def ffmpeg_loglevel(self):
        """Return FFmpeg log level."""
        return self._ffmpeg_loglevel

    @property
    def ffmpeg_recoverable_errors(self):
        """Return FFmpeg recoverable errors."""
        return self._ffmpeg_recoverable_errors

    @property
    def ffprobe_loglevel(self):
        """Return ffprobe log level."""
        return self._ffprobe_loglevel

    @property
    def static_mjpeg_streams(self):
        """Return static mjpeg streams."""
        return self._static_mjpeg_streams

    @property
    def logging(self):
        """Return logging config."""
        return self._logging
