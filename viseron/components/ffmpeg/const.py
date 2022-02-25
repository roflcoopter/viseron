"""FFmpeg constants."""
from typing import List

COMPONENT = "ffmpeg"

ENV_FFMPEG_PATH = "VISERON_FFMPEG_PATH"

STREAM_FORMAT_MAP = {
    "rtsp": {"protocol": "rtsp", "timeout_option": ["-stimeout", "5000000"]},
    "rtmp": {"protocol": "rtmp", "timeout_option": ["-rw_timeout", "5000000"]},
    "mjpeg": {"protocol": "http", "timeout_option": ["-timeout", "5000000"]},
}

RECORDER = "recorder"

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

# Hardware acceleration constands
HWACCEL_VAAPI = ["-hwaccel", "vaapi", "-vaapi_device", "/dev/dri/renderD128"]
HWACCEL_CUDA_DECODER_CODEC_MAP = {
    "h264": "h264_cuvid",
    "h265": "hevc_cuvid",
    "hevc": "hevc_cuvid",
}
HWACCEL_RPI3_DECODER_CODEC_MAP = {"h264": "h264_mmal"}
HWACCEL_RPI4_DECODER_CODEC_MAP = {"h264": "h264_v4l2m2m"}
HWACCEL_JETSON_NANO_DECODER_CODEC_MAP = {
    "h264": "h264_nvv4l2dec",
    "h265": "hevc_nvv4l2dec",
    "hevc": "hevc_nvv4l2dec",
}

# STREAM_SCHEMA constants
CONFIG_STREAM_FORMAT = "stream_format"
CONFIG_PROTOCOL = "protocol"
CONFIG_PATH = "path"
CONFIG_PORT = "port"
CONFIG_WIDTH = "width"
CONFIG_HEIGHT = "height"
CONFIG_FPS = "fps"
CONFIG_INPUT_ARGS = "input_args"
CONFIG_HWACCEL_ARGS = "hwaccel_args"
CONFIG_CODEC = "codec"
CONFIG_AUDIO_CODEC = "audio_codec"
CONFIG_RTSP_TRANSPORT = "rtsp_transport"
CONFIG_FILTER_ARGS = "filter_args"
CONFIG_PIX_FMT = "pix_fmt"
CONFIG_FRAME_TIMEOUT = "frame_timeout"

DEFAULT_STREAM_FORMAT = "rtsp"
DEFAULT_PROTOCOL = None
DEFAULT_WIDTH = None
DEFAULT_HEIGHT = None
DEFAULT_FPS = None
DEFAULT_INPUT_ARGS = None
DEFAULT_HWACCEL_ARGS: List["str"] = []
DEFAULT_CODEC = ""
DEFAULT_AUDIO_CODEC = "unset"
DEFAULT_RTSP_TRANSPORT = "tcp"
DEFAULT_FILTER_ARGS: List[str] = []
DEFAULT_PIX_FMT = "nv12"
DEFAULT_FRAME_TIMEOUT = 60


# RECORDER_SCHEMA constants
CONFIG_RECORDER_HWACCEL_ARGS = "hwaccel_args"
CONFIG_RECORDER_CODEC = "codec"
CONFIG_RECORDER_AUDIO_CODEC = "audio_codec"
CONFIG_RECORDER_FILTER_ARGS = "filter_args"
CONFIG_SEGMENTS_FOLDER = "segments_folder"

DEFAULT_RECORDER_HWACCEL_ARGS: List[str] = []
DEFAULT_RECORDER_CODEC = "copy"
DEFAULT_RECORDER_AUDIO_CODEC = "copy"
DEFAULT_RECORDER_FILTER_ARGS: List[str] = []
DEFAULT_SEGMENTS_FOLDER = "/segments"

# CAMERA_SCHEMA constants
CONFIG_CAMERA = "camera"

CONFIG_HOST = "host"
CONFIG_USERNAME = "username"
CONFIG_PASSWORD = "password"
CONFIG_GLOBAL_ARGS = "global_args"
CONFIG_SUBSTREAM = "substream"
CONFIG_FFMPEG_LOGLEVEL = "ffmpeg_loglevel"
CONFIG_FFMPEG_RECOVERABLE_ERRORS = "ffmpeg_recoverable_errors"
CONFIG_FFPROBE_LOGLEVEL = "ffprobe_loglevel"
CONFIG_RECORDER = "recorder"

DEFAULT_USERNAME = None
DEFAULT_PASSWORD = None
DEFAULT_GLOBAL_ARGS = ["-hide_banner"]
DEFAULT_FFMPEG_LOGLEVEL = "error"
DEFAULT_FFMPEG_RECOVERABLE_ERRORS = [
    "error while decoding MB",
    "Application provided invalid, non monotonically increasing dts to muxer in stream",
]
DEFAULT_FFPROBE_LOGLEVEL = "error"
