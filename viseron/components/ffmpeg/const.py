"""FFmpeg constants."""
import logging
from typing import Final

COMPONENT = "ffmpeg"

DESC_COMPONENT = "FFmpeg Configuration."

ENV_FFMPEG_PATH = "VISERON_FFMPEG_PATH"

STREAM_FORMAT_MAP = {
    "rtsp": {"protocol": "rtsp", "timeout_option": ["-timeout", "5000000"]},
    "rtmp": {"protocol": "rtmp", "timeout_option": ["-rw_timeout", "5000000"]},
    "mjpeg": {"protocol": "http", "timeout_option": ["-timeout", "5000000"]},
}

RECORDER = "recorder"

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

FFMPEG_LOGLEVELS = {
    "quiet": logging.CRITICAL,
    "panic": logging.CRITICAL,
    "fatal": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "verbose": logging.DEBUG,
    "debug": logging.DEBUG,
    "trace": logging.DEBUG,
}

FFPROBE_LOGLEVELS = FFMPEG_LOGLEVELS
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
CONFIG_VIDEO_FILTERS = "video_filters"
CONFIG_PIX_FMT = "pix_fmt"
CONFIG_FRAME_TIMEOUT = "frame_timeout"

DEFAULT_STREAM_FORMAT = "rtsp"
DEFAULT_PROTOCOL: Final = None
DEFAULT_WIDTH: Final = None
DEFAULT_HEIGHT: Final = None
DEFAULT_FPS: Final = None
DEFAULT_INPUT_ARGS: Final = None
DEFAULT_HWACCEL_ARGS: list["str"] = []
DEFAULT_CODEC = "unset"
DEFAULT_AUDIO_CODEC = "unset"
DEFAULT_RTSP_TRANSPORT = "tcp"
DEFAULT_VIDEO_FILTERS: list[str] = []
DEFAULT_PIX_FMT = "nv12"
DEFAULT_FRAME_TIMEOUT = 60

DESC_STREAM_FORMAT = "FFmpeg stream format."
DESC_PROTOCOL = "Stream protocol."
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
DESC_INPUT_ARGS = "A list of FFmpeg input arguments."
DESC_HWACCEL_ARGS = "A list of FFmpeg hardware acceleration arguments."
DESC_CODEC = (
    "FFmpeg video decoder codec, eg <code>h264_cuvid</code><br>"
    "Will use FFprobe to get this information if not given, "
    "see <a href=#ffprobe-stream-information>FFprobe stream information.</a>"
)
DESC_AUDIO_CODEC = (
    "Audio codec of the stream, eg <code>aac</code>.<br>"
    "Will use FFprobe to get this information if not given, "
    "see <a href=#ffprobe-stream-information>FFprobe stream information.</a>"
)
DESC_RTSP_TRANSPORT = (
    "Sets RTSP transport protocol. Change this if your camera doesn't support TCP."
)
DESC_VIDEO_FILTERS = (
    "A list of FFmpeg filter arguments. "
    "These filters are applied <b>before</b> Viseron receives the image for processing."
)
DESC_PIX_FMT = (
    "Only change this if the decoder you are using does not support <code>nv12</code>, "
    "as <code>nv12</code> is more efficient."
)
DESC_FRAME_TIMEOUT = (
    "A timeout in seconds. If a frame has not been received in this "
    "time period FFmpeg will be restarted."
)

# RECORDER_SCHEMA constants
CONFIG_RECORDER_HWACCEL_ARGS = "hwaccel_args"
CONFIG_RECORDER_CODEC = "codec"
CONFIG_RECORDER_AUDIO_CODEC = "audio_codec"
CONFIG_RECORDER_VIDEO_FILTERS = "video_filters"
CONFIG_RECORDER_AUDIO_FILTERS = "audio_filters"
CONFIG_SEGMENTS_FOLDER = "segments_folder"
CONFIG_RECORDER_OUPTUT_ARGS = "output_args"

DEFAULT_RECORDER_HWACCEL_ARGS: list[str] = []
DEFAULT_RECORDER_CODEC = "copy"
DEFAULT_RECORDER_AUDIO_CODEC = "unset"
DEFAULT_RECORDER_VIDEO_FILTERS: list[str] = []
DEFAULT_RECORDER_AUDIO_FILTERS: list[str] = []
DEFAULT_RECORDER_OUTPUT_ARGS: list[str] = []
DEFAULT_SEGMENTS_FOLDER = "/segments"

DESC_RECORDER_HWACCEL_ARGS = "FFmpeg encoder hardware acceleration arguments."
DESC_RECORDER_CODEC = "FFmpeg video encoder codec, eg <code>h264_nvenc</code>."
DESC_RECORDER_AUDIO_CODEC = (
    "FFmpeg audio encoder codec, eg <code>aac</code>.<br>"
    "If your source has audio and you want to remove it, set this to <code>null</code>."
)
DESC_RECORDER_VIDEO_FILTERS = (
    "A list of FFmpeg filter arguments. "
    "These filters are applied to the recorder videos."
)
DESC_RECORDER_AUDIO_FILTERS = (
    "A list of FFmpeg audio filter arguments. "
    "These filters are applied to the recorder videos."
)
DESC_RECORDER_OUTPUT_ARGS = "FFmpeg encoder output arguments."
DESC_SEGMENTS_FOLDER = (
    "What folder to store FFmpeg segments in. "
    "Segments are used to produce recordings so you should not need to change this."
)
DESC_RECORDER_FFMPEG_LOGLEVEL = (
    "Sets the FFmpeg loglevel for the recorder.<br>Should only be used in debugging"
    " purposes."
)


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
CONFIG_RAW_COMMAND = "raw_command"
CONFIG_RECORD_ONLY = "record_only"

DEFAULT_USERNAME: Final = None
DEFAULT_PASSWORD: Final = None
DEFAULT_GLOBAL_ARGS = ["-hide_banner"]
DEFAULT_SUBSTREAM: Final = None
DEFAULT_FFMPEG_LOGLEVEL = "error"
DEFAULT_FFMPEG_RECOVERABLE_ERRORS = [
    "error while decoding MB",
    "Application provided invalid, non monotonically increasing dts to muxer in stream",
    "Last message repeated",
    "non-existing PPS 0 referenced",
    "no frame!",
    "decode_slice_header error",
    "failed to delete old segment",
]
DEFAULT_FFPROBE_LOGLEVEL = "error"
DEFAULT_RAW_COMMAND: Final = None
DEFAULT_RECORD_ONLY = False

DESC_CAMERA = "Camera domain config."
DESC_HOST = "IP or hostname of camera."
DESC_USERNAME = "Username for the camera stream."
DESC_PASSWORD = "Password for the camera stream."
DESC_GLOBAL_ARGS = (
    "A valid list of FFmpeg arguments. "
    "These are applied before the <code>input_args</code>."
)
DESC_SUBSTREAM = (
    "Substream to perform image processing on. Very effective for reducing system load."
)
DESC_FFMPEG_LOGLEVEL = (
    "Sets the loglevel for FFmpeg.<br>Should only be used in debugging purposes."
)
DESC_FFMPEG_RECOVERABLE_ERRORS = (
    "FFmpeg sometimes print errors that are not fatal, "
    "but are preventing Viseron from reading the stream.<br>"
    "If you get errors like <code>Error starting decoder pipe!</code>, "
    "see <a href=#recoverable-errors>recoverable errors</a> below."
)
DESC_FFPROBE_LOGLEVEL = (
    "Sets the loglevel for FFprobe.<br> Should only be used in debugging purposes."
)
DESC_RECORDER = "Recorder config."
DESC_RAW_COMMAND = (
    "A raw FFmpeg command to use instead of the generated one. "
    "This is useful if you want to use sources that Viseron does not support. "
    "This is an advanced option and should only be used if you know what you are doing."
    "<br>See <a href=#raw-command>Raw command</a> for more information."
)
DESC_RECORD_ONLY = (
    "Only record the camera stream, do not process it. "
    "This is useful if you only want to record the stream and not do any processing "
    "like object detection.<br>"
    "Be aware that this will record the main stream, making substream redundant. "
    "Still images will not work either unless you have setup `still_image`."
)
