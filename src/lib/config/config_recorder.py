from voluptuous import All, Optional, Range, Schema

from .config_logging import LoggingConfig, SCHEMA as LOGGING_SCHEMA


SCHEMA = Schema(
    {
        Optional("lookback", default=5): All(int, Range(min=0)),
        Optional("timeout", default=10): All(int, Range(min=0)),
        Optional("retain", default=7): All(int, Range(min=1)),
        Optional("folder", default="/recordings"): str,
        Optional("extension", default="mp4"): str,
        Optional("hwaccel_args", default=[]): [str],
        Optional("codec", default="copy"): str,
        Optional("filter_args", default=[]): [str],
        Optional("segments_folder", default="/segments"): str,
        Optional("thumbnail", default={}): {
            Optional("save_to_disk", default=False): bool,
            Optional("send_to_mqtt", default=False): bool,
        },
        Optional("logging"): LOGGING_SCHEMA,
    }
)


class Thumbnail:
    def __init__(self, thumbnail):
        self._save_to_disk = thumbnail["save_to_disk"]
        self._send_to_mqtt = thumbnail["send_to_mqtt"]

    @property
    def save_to_disk(self):
        return self._save_to_disk

    @property
    def send_to_mqtt(self):
        return self._send_to_mqtt


class RecorderConfig:
    schema = SCHEMA

    def __init__(self, recorder):
        self._lookback = recorder["lookback"]
        self._timeout = recorder["timeout"]
        self._retain = recorder["retain"]
        self._folder = recorder["folder"]
        self._extension = recorder["extension"]
        self._hwaccel_args = recorder["hwaccel_args"]
        self._codec = recorder["codec"]
        self._filter_args = recorder["filter_args"]
        self._segments_folder = recorder["segments_folder"]
        self._thumbnail = Thumbnail(recorder["thumbnail"])
        self._logging = None
        if recorder.get("logging", None):
            self._logging = LoggingConfig(recorder["logging"])

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
    def hwaccel_args(self):
        return self._hwaccel_args

    @property
    def codec(self):
        return ["-c:v", self._codec]

    @property
    def filter_args(self):
        return self._filter_args

    @property
    def segments_folder(self):
        return self._segments_folder

    @property
    def thumbnail(self):
        return self._thumbnail

    @property
    def logging(self):
        return self._logging
