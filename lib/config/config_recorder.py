import logging

from voluptuous import (
    All,
    Range,
    Schema,
    Optional,
)

LOGGER = logging.getLogger(__name__)

RECORDER_GLOBAL_ARGS = ["-loglevel", "panic"]

SCHEMA = Schema(
    {
        Optional("lookback", default=10): All(int, Range(min=0)),
        Optional("timeout", default=10): All(int, Range(min=0)),
        Optional("retain", default=7): All(int, Range(min=1)),
        Optional("folder", default="/recordings"): str,
        Optional("extension", default="mp4"): str,
        Optional("global_args", default=RECORDER_GLOBAL_ARGS): list,
        Optional("hwaccel_args", default=[]): list,
        Optional("output_args", default=[]): list,
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
        self._output_args = recorder.output_args

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
    def output_args(self):
        return self._output_args
