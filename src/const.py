import cv2

CONFIG_PATH = "/config/config.yaml"
SECRETS_PATH = "/config/secrets.yaml"
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
    "-stimeout",
    "5000000",
    "-use_wallclock_as_timestamps",
    "1",
    "-vsync",
    "0",
]
CAMERA_HWACCEL_ARGS = []
CAMERA_OUTPUT_ARGS = ["-f", "rawvideo", "-pix_fmt", "nv12", "pipe:1"]
CAMERA_SEGMENT_ARGS = [
    "-f",
    "segment",
    "-segment_time",
    "10",
    "-segment_format",
    "mp4",
    "-reset_timestamps",
    "1",
    "-strftime",
    "1",
    "-c",
    "copy",
    "-an",
    "-map",
    "0",
]

ENCODER_CODEC = ""

ENV_CUDA_SUPPORTED = "VISERON_CUDA_SUPPORTED"
ENV_VAAPI_SUPPORTED = "VISERON_VAAPI_SUPPORTED"
ENV_OPENCL_SUPPORTED = "VISERON_OPENCL_SUPPORTED"
ENV_RASPBERRYPI3 = "VISERON_RASPBERRYPI3"

FFMPEG_RECOVERABLE_ERRORS = ["error while decoding MB"]

HWACCEL_VAAPI = ["-hwaccel", "vaapi", "-vaapi_device", "/dev/dri/renderD128"]
HWACCEL_VAAPI_ENCODER_FILTER = ["-vf", "format=nv12|vaapi,hwupload"]
HWACCEL_VAAPI_ENCODER_CODEC = "h264_vaapi"

HWACCEL_CUDA_DECODER_CODEC_MAP = {"h264": "h264_cuvid", "h265": "hevc_cuvid"}
HWACCEL_CUDA_ENCODER_CODEC = "h264_nvenc"

HWACCEL_RPI3_DECODER_CODEC_MAP = {"h264": "h264_mmal"}
HWACCEL_RPI3_ENCODER_CODEC = "h264_omx"

RECORDER_GLOBAL_ARGS = ["-hide_banner"]
RECORDER_HWACCEL_ARGS = []

LOG_LEVELS = {
    "CRITICAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}

FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SIZE = 0.6
FONT_THICKNESS = 1
