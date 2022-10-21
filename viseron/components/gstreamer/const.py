"""GStreamer constants."""
import logging
from typing import List

COMPONENT = "gstreamer"

DESC_COMPONENT = "GStreamer Configuration."

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
CONFIG_AUDIO_PIPELINE = "audio_pipeline"
CONFIG_RTSP_TRANSPORT = "rtsp_transport"
CONFIG_FRAME_TIMEOUT = "frame_timeout"

DEFAULT_STREAM_FORMAT = "rtsp"
DEFAULT_PROTOCOL = None
DEFAULT_WIDTH = None
DEFAULT_HEIGHT = None
DEFAULT_FPS = None
DEFAULT_CODEC = "unset"
DEFAULT_AUDIO_CODEC = "unset"
DEFAULT_AUDIO_PIPELINE = "unset"
DEFAULT_RTSP_TRANSPORT = "tcp"
DEFAULT_FRAME_TIMEOUT = 60

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


# CAMERA_SCHEMA constants
CONFIG_CAMERA = "camera"

CONFIG_HOST = "host"
CONFIG_USERNAME = "username"
CONFIG_PASSWORD = "password"
CONFIG_GSTREAMER_LOGLEVEL = "gstreamer_loglevel"
CONFIG_GSTREAMER_RECOVERABLE_ERRORS = "gstreamer_recoverable_errors"
CONFIG_FFPROBE_LOGLEVEL = "ffprobe_loglevel"
CONFIG_RECORDER = "recorder"

DEFAULT_USERNAME = None
DEFAULT_PASSWORD = None
DEFAULT_GSTREAMER_LOGLEVEL = "error"
DEFAULT_GSTREAMER_RECOVERABLE_ERRORS: List[str] = [
    "dconf will not work properly",
    "decode_slice_header error",
    "no frame!",
    "left block unavailable for requested intra mode",
    "error while decoding MB",
    "decreasing DTS value",
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

DESC_MUXER = "GStreamer segment muxer."
DESC_RECORDER_HWACCEL_ARGS = "<b>FFmpeg</b> encoder hardware acceleration arguments."
DESC_RECORDER_CODEC = "<b>FFmpeg</b> video encoder codec, eg <code>h264_nvenc</code>."
DESC_RECORDER_AUDIO_CODEC = "<b>FFmpeg</b> audio encoder codec, eg <code>aac</code>."
DESC_RECORDER_FILTER_ARGS = "<b>FFmpeg</b> encoder filter arguments."
DESC_SEGMENTS_FOLDER = (
    "What folder to store GStreamer segments in. "
    "Segments are used to produce recordings so you should not need to change this."
)
