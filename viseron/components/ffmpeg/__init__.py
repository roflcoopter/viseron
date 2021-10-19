"""FFmpeg component."""

import logging
import os
from typing import List

import voluptuous as vol

from viseron import Viseron
from viseron.const import ENV_CUDA_SUPPORTED, ENV_VAAPI_SUPPORTED
from viseron.domains.camera import (
    BASE_CONFIG_SCHEMA as BASE_CAMERA_CONFIG_SCHEMA,
    DEFAULT_RECORDER,
    RECORDER_SCHEMA as BASE_RECORDER_SCHEMA,
)

from .camera import Camera
from .const import (
    COMPONENT,
    CONFIG_AUDIO_CODEC,
    CONFIG_CODEC,
    CONFIG_FFMPEG_LOGLEVEL,
    CONFIG_FFMPEG_RECOVERABLE_ERRORS,
    CONFIG_FFPROBE_LOGLEVEL,
    CONFIG_FILTER_ARGS,
    CONFIG_FPS,
    CONFIG_FRAME_TIMEOUT,
    CONFIG_GLOBAL_ARGS,
    CONFIG_HEIGHT,
    CONFIG_HOST,
    CONFIG_HWACCEL_ARGS,
    CONFIG_INPUT_ARGS,
    CONFIG_PASSWORD,
    CONFIG_PATH,
    CONFIG_PIX_FMT,
    CONFIG_PORT,
    CONFIG_RECORDER,
    CONFIG_RTSP_TRANSPORT,
    CONFIG_SEGMENTS_FOLDER,
    CONFIG_STREAM_FORMAT,
    CONFIG_SUBSTREAM,
    CONFIG_USERNAME,
    CONFIG_WIDTH,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_CODEC,
    DEFAULT_FFMPEG_LOGLEVEL,
    DEFAULT_FFMPEG_RECOVERABLE_ERRORS,
    DEFAULT_FFPROBE_LOGLEVEL,
    DEFAULT_FILTER_ARGS,
    DEFAULT_FPS,
    DEFAULT_FRAME_TIMEOUT,
    DEFAULT_GLOBAL_ARGS,
    DEFAULT_HEIGHT,
    DEFAULT_HWACCEL_ARGS,
    DEFAULT_INPUT_ARGS,
    DEFAULT_PASSWORD,
    DEFAULT_PIX_FMT,
    DEFAULT_RTSP_TRANSPORT,
    DEFAULT_SEGMENTS_FOLDER,
    DEFAULT_STREAM_FORMAT,
    DEFAULT_USERNAME,
    DEFAULT_WIDTH,
    FFMPEG_LOG_LEVELS,
    HWACCEL_VAAPI,
    STREAM_FORMAT_MAP,
)


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


STREAM_SCEHMA = BASE_CAMERA_CONFIG_SCHEMA.extend(
    {
        vol.Optional(CONFIG_STREAM_FORMAT, default=DEFAULT_STREAM_FORMAT): vol.In(
            STREAM_FORMAT_MAP.keys()
        ),
        vol.Required(CONFIG_PATH): vol.All(str, vol.Length(min=1)),
        vol.Required(CONFIG_PORT): vol.All(int, vol.Range(min=1)),
        vol.Optional(CONFIG_WIDTH, default=DEFAULT_WIDTH): vol.Maybe(int),
        vol.Optional(CONFIG_HEIGHT, default=DEFAULT_HEIGHT): vol.Maybe(int),
        vol.Optional(CONFIG_FPS, default=DEFAULT_FPS): vol.Maybe(
            vol.All(int, vol.Range(min=1))
        ),
        vol.Optional(CONFIG_INPUT_ARGS, default=DEFAULT_INPUT_ARGS): vol.Maybe(list),
        vol.Optional(
            CONFIG_HWACCEL_ARGS, default=DEFAULT_HWACCEL_ARGS
        ): check_for_hwaccels,
        vol.Optional(CONFIG_CODEC, default=DEFAULT_CODEC): str,
        vol.Optional(CONFIG_AUDIO_CODEC, default=DEFAULT_AUDIO_CODEC): vol.Maybe(str),
        vol.Optional(CONFIG_RTSP_TRANSPORT, default=DEFAULT_RTSP_TRANSPORT): vol.Any(
            "tcp", "udp", "udp_multicast", "http"
        ),
        vol.Optional(CONFIG_FILTER_ARGS, default=DEFAULT_FILTER_ARGS): list,
        vol.Optional(CONFIG_PIX_FMT, default=DEFAULT_PIX_FMT): vol.Any(
            "nv12", "yuv420p"
        ),
        vol.Optional(CONFIG_FRAME_TIMEOUT, default=DEFAULT_FRAME_TIMEOUT): int,
    }
)

RECORDER_SCHEMA = BASE_RECORDER_SCHEMA.extend(
    {
        vol.Optional(CONFIG_HWACCEL_ARGS, default=DEFAULT_HWACCEL_ARGS): [str],
        vol.Optional(CONFIG_CODEC, default=DEFAULT_CODEC): str,
        vol.Optional(CONFIG_AUDIO_CODEC, default=DEFAULT_AUDIO_CODEC): str,
        vol.Optional(CONFIG_FILTER_ARGS, default=DEFAULT_FILTER_ARGS): [str],
        vol.Optional(CONFIG_SEGMENTS_FOLDER, default=DEFAULT_SEGMENTS_FOLDER): str,
    }
)

FFMPEG_LOGLEVEL_SCEHMA = vol.Schema(vol.In(FFMPEG_LOG_LEVELS.keys()))

CAMERA_SCHEMA = STREAM_SCEHMA.extend(
    {
        vol.Required(CONFIG_HOST): vol.All(str, vol.Length(min=1)),
        vol.Optional(CONFIG_USERNAME, default=DEFAULT_USERNAME): vol.Maybe(
            vol.All(str, vol.Length(min=1))
        ),
        vol.Optional(CONFIG_PASSWORD, default=DEFAULT_PASSWORD): vol.Maybe(
            vol.All(str, vol.Length(min=1))
        ),
        vol.Optional(CONFIG_GLOBAL_ARGS, default=DEFAULT_GLOBAL_ARGS): list,
        vol.Optional(CONFIG_SUBSTREAM): STREAM_SCEHMA,
        vol.Optional(
            CONFIG_FFMPEG_LOGLEVEL, default=DEFAULT_FFMPEG_LOGLEVEL
        ): FFMPEG_LOGLEVEL_SCEHMA,
        vol.Optional(
            CONFIG_FFMPEG_RECOVERABLE_ERRORS, default=DEFAULT_FFMPEG_RECOVERABLE_ERRORS
        ): [str],
        vol.Optional(
            CONFIG_FFPROBE_LOGLEVEL, default=DEFAULT_FFPROBE_LOGLEVEL
        ): FFMPEG_LOGLEVEL_SCEHMA,
        vol.Optional(CONFIG_RECORDER, default=DEFAULT_RECORDER): RECORDER_SCHEMA,
    }
)

CONFIG_CAMERAS = "cameras"

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: {
            vol.Required(CONFIG_CAMERAS): [CAMERA_SCHEMA],
        },
    },
    extra=vol.ALLOW_EXTRA,
)

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config):
    """Set up the ffmpeg component."""
    config = config[COMPONENT]
    vis.data[COMPONENT] = {}

    LOGGER.debug(config)
    for camera in config[CONFIG_CAMERAS]:
        LOGGER.debug(camera)
        camera = Camera(vis, camera)

    return True
