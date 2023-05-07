"""GStreamer constants."""
from __future__ import annotations

import logging
from typing import Final, TypedDict

import gi

COMPONENT = "gstreamer"

DESC_COMPONENT = "GStreamer Configuration."

ENV_GSTREAMER_PATH = "VISERON_GSTREAMER_PATH"

RECORDER = "recorder"

# pylint: disable=wrong-import-position,wrong-import-order
gi.require_version("Gst", "1.0")
from gi.repository import Gst  # type: ignore[attr-defined] # noqa: E402

# pylint: enable=wrong-import-position


class StreamFormat(TypedDict):
    """Stream format."""

    protocol: str
    plugin: str
    options: list[str]


# Pipeline constants
STREAM_FORMAT_MAP: dict[str, StreamFormat] = {
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

CONFIG_LOGLEVEL_TO_GSTREAMER = {
    "error": Gst.DebugLevel.ERROR,
    "warning": Gst.DebugLevel.WARNING,
    "fixme": Gst.DebugLevel.FIXME,
    "info": Gst.DebugLevel.INFO,
    "debug": Gst.DebugLevel.DEBUG,
    "trace": Gst.DebugLevel.TRACE,
}

GSTREAMER_LOGLEVEL_TO_PYTHON = {
    Gst.DebugLevel.NONE: logging.NOTSET,
    Gst.DebugLevel.ERROR: logging.ERROR,
    Gst.DebugLevel.WARNING: logging.WARNING,
    Gst.DebugLevel.FIXME: logging.INFO,
    Gst.DebugLevel.INFO: logging.INFO,
    Gst.DebugLevel.DEBUG: logging.DEBUG,
    Gst.DebugLevel.LOG: logging.DEBUG,
    Gst.DebugLevel.TRACE: logging.DEBUG,
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
CONFIG_AUDIO_PIPELINE = "audio_pipeline"
CONFIG_RTSP_TRANSPORT = "rtsp_transport"
CONFIG_FRAME_TIMEOUT = "frame_timeout"
CONFIG_OUTPUT_ELEMENT = "output_element"
CONFIG_RAW_PIPELINE = "raw_pipeline"


DEFAULT_STREAM_FORMAT = "rtsp"
DEFAULT_PROTOCOL: Final = None
DEFAULT_WIDTH: Final = None
DEFAULT_HEIGHT: Final = None
DEFAULT_FPS: Final = None
DEFAULT_CODEC = "unset"
DEFAULT_AUDIO_CODEC = "unset"
DEFAULT_AUDIO_PIPELINE = "unset"
DEFAULT_RTSP_TRANSPORT = "tcp"
DEFAULT_FRAME_TIMEOUT = 60
DEFAULT_OUTPUT_ELEMENT: str = ""
DEFAULT_RAW_PIPELINE: Final = None

DESC_STREAM_FORMAT = "Stream format."
DESC_PROTOCOL = "Stream protocol"
DESC_PATH = "Path to the camera stream, eg <code>/Streaming/Channels/101/</code>."
DESC_PORT = "Port for the camera stream,"
DESC_WIDTH = (
    "Width of the stream.<br>"
    "Will use FFprobe to get this information if not given, "
    "see <a href=#ffprobe-stream-information>FFprobe stream information.</a>"
)
DESC_HEIGHT = (
    "Height of the stream.<br>"
    "Will use FFprobe to get this information if not given, "
    "see <a href=#ffprobe-stream-information>FFprobe stream information.</a>"
)
DESC_FPS = (
    "FPS of the stream.<br>"
    "Will use FFprobe to get this information if not given, "
    "see <a href=#ffprobe-stream-information>FFprobe stream information.</a>"
)
DESC_CODEC = (
    "Stream codec, eg <code>h264</code><br>"
    "Will use FFprobe to get this information if not given, "
    "see <a href=#ffprobe-stream-information>FFprobe stream information.</a>"
)
DESC_AUDIO_CODEC = (
    "Stream audio codec, eg <code>aac</code><br>"
    "Will use FFprobe to get this information if not given, "
    "see <a href=#ffprobe-stream-information>FFprobe stream information.</a>"
)
DESC_AUDIO_PIPELINE = "GStreamer audio pipeline."
DESC_RTSP_TRANSPORT = (
    "Sets RTSP transport protocol. Change this if your camera doesn't support TCP."
)
DESC_FRAME_TIMEOUT = (
    "A timeout in seconds. If a frame has not been received in this "
    "time period GStreamer will be restarted."
)
DESC_OUTPUT_ELEMENT = (
    "A GStreamer pipeline element that is added to the generated pipeline. "
    "It can be used to perform additional filtering on the frames that Viseron is "
    "processing."
)
DESC_RAW_PIPELINE = (
    "A raw GStreamer pipeline that will be used instead of the generated pipeline. "
    "This is an advanced option and should only be used if you know what you are doing."
    " See <a href=#raw-pipeline>Raw pipeline</a> for more information."
)


# CAMERA_SCHEMA constants
CONFIG_CAMERA = "camera"

CONFIG_HOST = "host"
CONFIG_USERNAME = "username"
CONFIG_PASSWORD = "password"
CONFIG_GSTREAMER_LOGLEVEL = "gstreamer_loglevel"
CONFIG_GSTREAMER_RECOVERABLE_ERRORS = "gstreamer_recoverable_errors"
CONFIG_FFPROBE_LOGLEVEL = "ffprobe_loglevel"
CONFIG_RECORDER = "recorder"

DEFAULT_USERNAME: Final = None
DEFAULT_PASSWORD: Final = None
DEFAULT_GSTREAMER_LOGLEVEL = "error"
DEFAULT_GSTREAMER_RECOVERABLE_ERRORS: list[str] = [
    "Last message repeated",
    "dconf will not work properly",
    "decode_slice_header error",
    "no frame!",
    "left block unavailable for requested intra mode",
    "error while decoding MB",
    "decreasing DTS value",
    "non-existing PPS 0 referenced",
]
DEFAULT_FFPROBE_LOGLEVEL = "error"


DESC_CAMERA = "Camera domain config."
DESC_HOST = "IP or hostname of camera."
DESC_USERNAME = "Username for the camera stream."
DESC_PASSWORD = "Password for the camera stream."
DESC_GSTREAMER_LOGLEVEL = (
    "Sets the loglevel for GStreamer.<br>Should only be used in debugging purposes."
)
DESC_GSTREAMER_RECOVERABLE_ERRORS = (
    "GStreamer sometimes print errors that are not fatal, "
    "but are preventing Viseron from reading the stream.<br>"
    "If you get errors like <code>Error starting decoder pipe!</code>, "
    "see <a href=#recoverable-errors>recoverable errors</a> below."
)
DESC_FFPROBE_LOGLEVEL = (
    "Sets the loglevel for FFprobe.<br> Should only be used in debugging purposes."
)
DESC_RECORDER = "Recorder config."


# RECORDER_SCHEMA constants
CONFIG_MUXER = "muxer"

DEFAULT_MUXER = "mp4mux"

DESC_MUXER = "GStreamer segment muxer."
DESC_SEGMENTS_FOLDER = (
    "What folder to store GStreamer segments in. "
    "Segments are used to produce recordings so you should not need to change this."
)
