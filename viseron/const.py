"""Constants."""
import os
from typing import Final

import cv2

DEFAULT_PORT = 9999
CONFIG_DIR = os.getenv("VISERON_CONFIG_DIR", "/config")
CONFIG_PATH = f"{CONFIG_DIR}/config.yaml"
SECRETS_PATH = f"{CONFIG_DIR}/secrets.yaml"
STORAGE_PATH = f"{CONFIG_DIR}/.viseron"
VISERON_LOG_PATH = f"{CONFIG_DIR}/viseron.log"
TEMP_DIR = "/tmp/viseron"
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
            trigger_event_recording: true

      camera_2:  # Attach detector to the configured camera_2 above
        fps: 1
        labels:
          - label: person
            confidence: 0.75
            trigger_event_recording: true


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
CAMERA_SEGMENT_DURATION = 5


# Environment variables
ENV_CUDA_SUPPORTED = "VISERON_CUDA_SUPPORTED"
ENV_VAAPI_SUPPORTED = "VISERON_VAAPI_SUPPORTED"
ENV_OPENCL_SUPPORTED = "VISERON_OPENCL_SUPPORTED"
ENV_RASPBERRYPI3 = "VISERON_RASPBERRYPI3"
ENV_RASPBERRYPI4 = "VISERON_RASPBERRYPI4"
ENV_RASPBERRYPI5 = "VISERON_RASPBERRYPI5"
ENV_JETSON_NANO = "VISERON_JETSON_NANO"
ENV_PROFILE_MEMORY = "VISERON_PROFILE_MEMORY"
ENV_LOG_MAX_BYTES = "VISERON_LOG_MAX_BYTES"
ENV_LOG_BACKUP_COUNT = "VISERON_LOG_BACKUP_COUNT"
ENV_DEV_WARNINGS = "VISERON_DEV_WARNINGS"


FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SIZE = 0.6
FONT_THICKNESS = 1


TOPIC_STATIC_MJPEG_STREAMS = "static_mjepg_streams"

# Viseron.data constants
LOADING: Final = "loading"
LOADED: Final = "loaded"
FAILED: Final = "failed"

# Signal constants
VISERON_SIGNAL_SHUTDOWN: Final = "shutdown"
VISERON_SIGNAL_LAST_WRITE: Final = "last_write"
VISERON_SIGNAL_STOPPING: Final = "stopping"

# State constants
STATE_ON = "on"
STATE_OFF = "off"
STATE_UNKNOWN = "unknown"

# Event topic constants
EVENT_STATE_CHANGED = "state_changed"
EVENT_ENTITY_ADDED = "entity_added"
EVENT_DOMAIN_REGISTERED = "domain/registered/{domain}"
EVENT_DOMAIN_UNREGISTERED = "domain/unregistered/{domain}"
EVENT_DOMAIN_SETUP_STATUS = "domain/setup/{status}/{domain}/{identifier}"

# Setup constants
COMPONENT_RETRY_INTERVAL = 10
COMPONENT_RETRY_INTERVAL_MAX = 300
DOMAIN_RETRY_INTERVAL = 10
DOMAIN_RETRY_INTERVAL_MAX = 300
SLOW_SETUP_WARNING = 20
SLOW_DEPENDENCY_WARNING = 60


RESTART_EXIT_CODE = 100

# Database constants
INSERT: Final = "insert"
UPDATE: Final = "update"
DELETE: Final = "delete"
