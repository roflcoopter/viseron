"""Constants."""
from typing import List

from cv2 import FONT_HERSHEY_SIMPLEX

CONFIG_PATH = "/config/config.yaml"
SECRETS_PATH = "/config/secrets.yaml"
RECORDER_PATH = "/recordings"
DEFAULT_CONFIG = """
# See the README for the full list of configuration options.
cameras:
  - name: <camera friendly name>
    host: <ip address or hostname>
    port: <port the camera listens on>
    username: <if auth is enabled>
    password: <if auth is enabled>
    path: <URL path to the stream>

# MQTT is optional
#mqtt:
#  broker: <ip address or hostname of broker>
#  port: <port the broker listens on>
#  username: <if auth is enabled>
#  password: <if auth is enabled>
"""
THREAD_STORE_CATEGORY_NVR = "nvr"

CAMERA_GLOBAL_ARGS = ["-hide_banner"]
CAMERA_INPUT_ARGS = [
    "-avoid_negative_ts",
    "make_zero",
    "-fflags",
    "nobuffer",
    "-flags",
    "low_delay",
    "-strict",
    "experimental",
    "-fflags",
    "+genpts",
    "-use_wallclock_as_timestamps",
    "1",
    "-vsync",
    "0",
]
CAMERA_HWACCEL_ARGS: List["str"] = []
CAMERA_SEGMENT_DURATION = 5
CAMERA_SEGMENT_ARGS = [
    "-f",
    "segment",
    "-segment_time",
    str(CAMERA_SEGMENT_DURATION),
    "-reset_timestamps",
    "1",
    "-strftime",
    "1",
    "-c:v",
    "copy",
]

ENCODER_CODEC = ""

ENV_CUDA_SUPPORTED = "VISERON_CUDA_SUPPORTED"
ENV_VAAPI_SUPPORTED = "VISERON_VAAPI_SUPPORTED"
ENV_OPENCL_SUPPORTED = "VISERON_OPENCL_SUPPORTED"
ENV_RASPBERRYPI3 = "VISERON_RASPBERRYPI3"
ENV_RASPBERRYPI4 = "VISERON_RASPBERRYPI4"
ENV_JETSON_NANO = "VISERON_JETSON_NANO"
ENV_FFMPEG_PATH = "VISERON_FFMPEG_PATH"

FFMPEG_RECOVERABLE_ERRORS = [
    "error while decoding MB",
    "Application provided invalid, non monotonically increasing dts to muxer in stream",
]


HWACCEL_VAAPI = ["-hwaccel", "vaapi", "-vaapi_device", "/dev/dri/renderD128"]
HWACCEL_VAAPI_ENCODER_FILTER = ["-vf", "format=nv12|vaapi,hwupload"]
HWACCEL_VAAPI_ENCODER_CODEC = "h264_vaapi"

HWACCEL_CUDA_DECODER_CODEC_MAP = {"h264": "h264_cuvid", "h265": "hevc_cuvid"}
HWACCEL_CUDA_ENCODER_CODEC = "h264_nvenc"

HWACCEL_RPI3_DECODER_CODEC_MAP = {"h264": "h264_mmal"}
HWACCEL_RPI3_ENCODER_CODEC = "h264_omx"

HWACCEL_RPI4_DECODER_CODEC_MAP = {"h264": "h264_v4l2m2m"}
HWACCEL_RPI4_ENCODER_CODEC = "h264_v4l2m2m"

HWACCEL_JETSON_NANO_DECODER_CODEC_MAP = {
    "h264": "h264_nvmpi",
    "h265": "hevc_nvmpi",
}

RECORDER_GLOBAL_ARGS = ["-hide_banner"]
RECORDER_HWACCEL_ARGS: List[str] = []

LOG_LEVELS = {
    "CRITICAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}

FFMPEG_LOG_LEVELS = {
    "quiet": 50,
    "panic": 50,
    "fatal": 50,
    "error": 40,
    "warning": 30,
    "info": 20,
    "verbose": 10,
    "debug": 10,
    "trace": 10,
}

FFPROBE_TIMEOUT = 15

FONT = FONT_HERSHEY_SIMPLEX
FONT_SIZE = 0.6
FONT_THICKNESS = 1


TOPIC_STATIC_MJPEG_STREAMS = "static_mjepg_streams"

TOPIC_DECODE = "decode"
TOPIC_FRAME = "frame"
TOPIC_PROCESSED = "processed"
TOPIC_SCAN = "scan"

TOPIC_FRAME_DECODE = "/".join([TOPIC_FRAME, TOPIC_DECODE])
TOPIC_FRAME_SCAN = "/".join([TOPIC_FRAME, TOPIC_SCAN])
TOPIC_FRAME_PROCESSED = "/".join([TOPIC_FRAME, TOPIC_PROCESSED])

TOPIC_MOTION = "motion"
TOPIC_FRAME_DECODE_MOTION = "/".join(
    [
        TOPIC_FRAME_DECODE,
        TOPIC_MOTION,
    ]
)
TOPIC_FRAME_SCAN_MOTION = "/".join(
    [
        TOPIC_FRAME_SCAN,
        TOPIC_MOTION,
    ]
)
TOPIC_FRAME_PROCESSED_MOTION = "/".join(
    [
        TOPIC_FRAME_PROCESSED,
        TOPIC_MOTION,
    ]
)

TOPIC_OBJECT = "object"
TOPIC_FRAME_DECODE_OBJECT = "/".join(
    [
        TOPIC_FRAME_DECODE,
        TOPIC_OBJECT,
    ]
)
TOPIC_FRAME_SCAN_OBJECT = "/".join(
    [
        TOPIC_FRAME_SCAN,
        TOPIC_OBJECT,
    ]
)
TOPIC_FRAME_PROCESSED_OBJECT = "/".join(
    [
        TOPIC_FRAME_PROCESSED,
        TOPIC_OBJECT,
    ]
)

TOPIC_POST_PROCESSOR = "post_processor"
TOPIC_FRAME_SCAN_POSTPROC = "/".join([TOPIC_FRAME_SCAN, TOPIC_POST_PROCESSOR])

# UI constants
PREFIX_STATIC = "/ui/static/"
PATH_STATIC = "/src/viseron/webserver/assets/static"
PATH_TEMPLATES = "/src/viseron/webserver/assets/templates"
