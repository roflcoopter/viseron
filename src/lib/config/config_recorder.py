import logging
import os

from voluptuous import All, Optional, Range, Schema

from const import (
    ENCODER_CODEC,
    ENV_CUDA_SUPPORTED,
    ENV_RASPBERRYPI3,
    ENV_VAAPI_SUPPORTED,
    HWACCEL_CUDA_ENCODER_CODEC,
    HWACCEL_RPI3_ENCODER_CODEC,
    HWACCEL_VAAPI,
    HWACCEL_VAAPI_ENCODER_CODEC,
    HWACCEL_VAAPI_ENCODER_FILTER,
    RECORDER_GLOBAL_ARGS,
    RECORDER_HWACCEL_ARGS,
)

from .config_logging import SCHEMA as LOGGING_SCHEMA

LOGGER = logging.getLogger(__name__)


def check_for_hwaccels(hwaccel_args: list) -> list:
    if hwaccel_args:
        return hwaccel_args

    if os.getenv(ENV_VAAPI_SUPPORTED) == "true":
        return HWACCEL_VAAPI
    return hwaccel_args


def get_filter_args(filter_args: list) -> list:
    if filter_args:
        return filter_args

    if os.getenv(ENV_VAAPI_SUPPORTED) == "true":
        return HWACCEL_VAAPI_ENCODER_FILTER
    return filter_args


def get_codec() -> str:
    if os.getenv(ENV_CUDA_SUPPORTED) == "true":
        return HWACCEL_CUDA_ENCODER_CODEC
    if os.getenv(ENV_VAAPI_SUPPORTED) == "true":
        return HWACCEL_VAAPI_ENCODER_CODEC
    if os.getenv(ENV_RASPBERRYPI3) == "true":
        return HWACCEL_RPI3_ENCODER_CODEC
    return ENCODER_CODEC


SCHEMA = Schema(
    {
        Optional("lookback", default=5): All(int, Range(min=0)),
        Optional("timeout", default=10): All(int, Range(min=0)),
        Optional("retain", default=7): All(int, Range(min=1)),
        Optional("folder", default="/recordings"): str,
        Optional("extension", default="mp4"): str,
        Optional("global_args", default=RECORDER_GLOBAL_ARGS): list,
        Optional("hwaccel_args", default=RECORDER_HWACCEL_ARGS): check_for_hwaccels,
        Optional("codec", default=get_codec()): str,
        Optional("filter_args", default=[]): get_filter_args,
        Optional("logging"): LOGGING_SCHEMA,
    }
)


class RecorderConfig:
    schema = SCHEMA

    def __init__(self, recorder):
        self._lookback = recorder.lookback
        self._timeout = recorder.timeout
        self._retain = recorder.retain
        self._folder = recorder.folder
        self._extension = recorder.extension
        self._global_args = recorder.global_args
        self._hwaccel_args = recorder.hwaccel_args
        self._codec = recorder.codec
        self._filter_args = recorder.filter_args
        self._logging = getattr(recorder, "logging", None)

    @property
    def lookback(self):
        return self._lookback

    @property
    def timeout(self):
        return self._timeout

    @property
    def retain(self):
        return self._retain

    @property
    def folder(self):
        return self._folder

    @property
    def extension(self):
        return self._extension

    @property
    def global_args(self):
        return self._global_args

    @property
    def hwaccel_args(self):
        return self._hwaccel_args

    @property
    def codec(self):
        return ["-c:v", self._codec] if self._codec else []

    @property
    def filter_args(self):
        return self._filter_args

    @property
    def logging(self):
        return self._logging
