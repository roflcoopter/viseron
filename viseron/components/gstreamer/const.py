"""GStreamer constants."""
import logging
from typing import List

COMPONENT = "gstreamer"

ENV_GSTREAMER_PATH = "VISERON_GSTREAMER_PATH"

RECORDER = "recorder"


# Pipeline constants
STREAM_FORMAT_MAP = {
    "rtsp": {
        "protocol": "rtsp",
        "plugin": "rtspsrc",
        "options": [
            "latency=0",
        ],
    },
    "rtmp": {
        "protocol": "rtmp",
        "plugin": "rtmpsrc",
        "options": [
            "latency=0",
        ],
    },
    # Mjpeg not supported as of now
    # "mjpeg": {
    #     "protocol": "http",
    #     "plugin": "souphttpsrc",
    #     "options": [],
    # },
}


DEPAY_ELEMENT_MAP = {
    "hevc": "rtph265depay",
    "mjpeg": False,  # False means no depay element will be used
}

PARSE_ELEMENT_MAP = {
    "hevc": "h265parse",
    "mjpeg": "jpegparse",
}

DECODER_ELEMENT_MAP = {
    "hevc": "avdec_h265",
    "mjpeg": "jpegdec",
}

PIXEL_FORMAT = "NV12"

CAMERA_SEGMENT_DURATION = 5

GSTREAMER_LOGLEVELS = {
    "error": 1,
    "warning": 2,
    "fixme": 3,
    "info": 4,
    "debug": 5,
    "trace": 7,
}

LOGLEVEL_CONVERTER = {
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "fixme": logging.INFO,
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "trace": logging.DEBUG,
}

# STREAM_SCHEMA constants
CONFIG_STREAM_FORMAT = "stream_format"
CONFIG_PROTOCOL = "protocol"
CONFIG_PATH = "path"
CONFIG_PORT = "port"
CONFIG_WIDTH = "width"
CONFIG_HEIGHT = "height"
CONFIG_FPS = "fps"
CONFIG_CODEC = "codec"
CONFIG_AUDIO_CODEC = "audio_codec"
CONFIG_RTSP_TRANSPORT = "rtsp_transport"
CONFIG_FRAME_TIMEOUT = "frame_timeout"

DEFAULT_STREAM_FORMAT = "rtsp"
DEFAULT_PROTOCOL = None
DEFAULT_WIDTH = None
DEFAULT_HEIGHT = None
DEFAULT_FPS = None
DEFAULT_CODEC = ""
DEFAULT_AUDIO_CODEC = "unset"
DEFAULT_RTSP_TRANSPORT = "tcp"
DEFAULT_FRAME_TIMEOUT = 60


# CAMERA_SCHEMA constants
CONFIG_CAMERA = "camera"

CONFIG_HOST = "host"
CONFIG_USERNAME = "username"
CONFIG_PASSWORD = "password"
CONFIG_SUBSTREAM = "substream"
CONFIG_GSTREAMER_LOGLEVEL = "gstreamer_loglevel"
CONFIG_GSTREAMER_RECOVERABLE_ERRORS = "gstreamer_recoverable_errors"
CONFIG_FFPROBE_LOGLEVEL = "ffprobe_loglevel"
CONFIG_RECORDER = "recorder"

DEFAULT_USERNAME = None
DEFAULT_PASSWORD = None
DEFAULT_GSTREAMER_LOGLEVEL = "error"
DEFAULT_GSTREAMER_RECOVERABLE_ERRORS: List[str] = []
DEFAULT_FFPROBE_LOGLEVEL = "error"


# RECORDER_SCHEMA constants
CONFIG_MUXER = "muxer"
CONFIG_RECORDER_HWACCEL_ARGS = "hwaccel_args"
CONFIG_RECORDER_CODEC = "codec"
CONFIG_RECORDER_AUDIO_CODEC = "audio_codec"
CONFIG_RECORDER_FILTER_ARGS = "filter_args"
CONFIG_SEGMENTS_FOLDER = "segments_folder"

DEFAULT_MUXER = "mp4mux"
DEFAULT_RECORDER_HWACCEL_ARGS: List[str] = []
DEFAULT_RECORDER_CODEC = "copy"
DEFAULT_RECORDER_AUDIO_CODEC = "copy"
DEFAULT_RECORDER_FILTER_ARGS: List[str] = []
DEFAULT_SEGMENTS_FOLDER = "/segments"
