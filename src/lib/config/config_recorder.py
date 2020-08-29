import logging
import os

from const import (
    ENCODER_CODEC,
    RECORDER_GLOBAL_ARGS,
    RECORDER_HWACCEL_ARGS,
    ENV_CUDA_SUPPORTED,
    ENV_VAAPI_SUPPORTED,
    ENV_RASPBERRYPI3,
    HWACCEL_CUDA_ENCODER_CODEC,
    HWACCEL_RPI3_ENCODER_CODEC,
    HWACCEL_VAAPI,
    HWACCEL_VAAPI_ENCODER_FILTER,
    HWACCEL_VAAPI_ENCODER_CODEC,
)

from voluptuous import (
    All,
    Range,
    Schema,
    Optional,
)

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


def get_codec(codec: list) -> list:
    if codec:
        return codec

    if os.getenv(ENV_CUDA_SUPPORTED) == "true":
        return HWACCEL_CUDA_ENCODER_CODEC
    if os.getenv(ENV_VAAPI_SUPPORTED) == "true":
        return HWACCEL_VAAPI_ENCODER_CODEC
    if os.getenv(ENV_RASPBERRYPI3) == "true":
        return HWACCEL_RPI3_ENCODER_CODEC
    return codec


SCHEMA = Schema(
    {
        Optional("lookback", default=5): All(int, Range(min=0)),
        Optional("timeout", default=10): All(int, Range(min=0)),
        Optional("retain", default=7): All(int, Range(min=1)),
        Optional("folder", default="/recordings"): str,
        Optional("extension", default="mp4"): str,
        Optional("global_args", default=RECORDER_GLOBAL_ARGS): list,
        Optional("hwaccel_args", default=RECORDER_HWACCEL_ARGS): check_for_hwaccels,
        Optional("codec", default=ENCODER_CODEC): get_codec,
        Optional("filter_args", default=[]): get_filter_args,
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
        return ["-c:v"] + self._codec if self._codec else self._codec

    @property
    def filter_args(self):
        return self._filter_args
