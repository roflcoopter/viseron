"""Constants."""
from typing import List

from cv2 import FONT_HERSHEY_SIMPLEX

CONFIG_PATH = "/config/config.yaml"
SECRETS_PATH = "/config/secrets.yaml"
RECORDER_PATH = "/recordings"
DEFAULT_CONFIG = """# Thanks for trying out Viseron!
# This is a small walkthrough of the configuration to get you started.
# There are far more components and options available than what is listed here.
# See the documentation for the full list of configuration options.

## Start by adding some cameras
ffmpeg:
  camera:
    camera_1:  # This value has to be unique across all cameras
      name: <camera friendly name>
      host: <ip address or hostname of camera>
      port: <port the camera listens on>
      path: <URL path to the stream>
      username: <if auth is enabled>
      password: <if auth is enabled>

    camera_2:  # This value has to be unique across all cameras
      name: <camera friendly name>
      host: <ip address or hostname of camera>
      port: <port the camera listens on>
      path: <URL path to the stream>
      username: <if auth is enabled>
      password: <if auth is enabled>


## Then add an object detector
darknet:
  object_detector:
    cameras:
      camera_1:  # Attach detector to the configured camera_1 above
        fps: 1
        scan_on_motion_only: false  # Scan for objects even when there is no motion
        labels:
          - label: person
            confidence: 0.75
            trigger_recorder: true

      camera_2:  # Attach detector to the configured camera_2 above
        fps: 1
        labels:
          - label: person
            confidence: 0.75
            trigger_recorder: true


## You can also use motion detection
mog2:
  motion_detector:
    cameras:
      camera_2:  # Attach detector to the configured camera_2 above
        fps: 1


## To tie everything together we need to configure one more component.
nvr:
  camera_1:  # Run NVR for camera_1
  camera_2:  # Run NVR for camera_2

# Now you can restart Viseron and you should be good to go!
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
ENV_PROFILE_MEMORY = "VISERON_PROFILE_MEMORY"

FFMPEG_RECOVERABLE_ERRORS = [
    "error while decoding MB",
    "Application provided invalid, non monotonically increasing dts to muxer in stream",
]


RECORDER_GLOBAL_ARGS = ["-hide_banner"]
RECORDER_HWACCEL_ARGS: List[str] = []

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


# Viseron.data constants
LOADING = "loading"
LOADED = "loaded"
FAILED = "failed"
DOMAINS_TO_SETUP = "domains_to_setup"
DOMAIN_IDENTIFIERS = "domain_identifiers"
DOMAIN_SETUP_TASKS = "domain_setup_tasks"
REGISTERED_DOMAINS = "registered_domains"

# Signal constants
VISERON_SIGNAL_SHUTDOWN = "shutdown"

# State constants
STATE_ON = "on"
STATE_OFF = "off"
STATE_UNKNOWN = "unknown"

# Event topic constants
EVENT_STATE_CHANGED = "state_changed"
EVENT_ENTITY_ADDED = "entity_added"
EVENT_DOMAIN_REGISTERED = "domain/registered/{domain}"

# Setup constants
COMPONENT_RETRY_INTERVAL = 10
COMPONENT_RETRY_INTERVAL_MAX = 300
DOMAIN_RETRY_INTERVAL = 10
DOMAIN_RETRY_INTERVAL_MAX = 300
SLOW_SETUP_WARNING = 20
SLOW_DEPENDENCY_WARNING = 60
