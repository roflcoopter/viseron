"""Recorder config."""
from voluptuous import All, Optional, Range, Schema

from viseron.const import RECORDER_PATH

SCHEMA = Schema(
    {
        Optional("lookback", default=5): All(int, Range(min=0)),
        Optional("timeout", default=10): All(int, Range(min=0)),
        Optional("retain", default=7): All(int, Range(min=1)),
        Optional("folder", default=RECORDER_PATH): str,
        Optional("filename_pattern", default="%H:%M:%S"): str,
        Optional("extension", default="mp4"): str,
        Optional("hwaccel_args", default=[]): [str],
        Optional("codec", default="copy"): str,
        Optional("audio_codec", default="copy"): str,
        Optional("filter_args", default=[]): [str],
        Optional("segments_folder", default="/segments"): str,
        Optional("thumbnail", default={}): {
            Optional("save_to_disk", default=False): bool,
            Optional("filename_pattern", default="%H:%M:%S"): str,
            Optional("send_to_mqtt", default=False): bool,
        },
    }
)


class Thumbnail:
    """Thumbnail config."""

    def __init__(self, thumbnail):
        self._save_to_disk = thumbnail["save_to_disk"]
        self._filename_pattern = thumbnail["filename_pattern"]
        self._send_to_mqtt = thumbnail["send_to_mqtt"]

    @property
    def save_to_disk(self):
        """Return if thumbnail should be saved to disk."""
        return self._save_to_disk

    @property
    def filename_pattern(self):
        """Return thumbnail filename strftime pattern."""
        return self._filename_pattern

    @property
    def send_to_mqtt(self):
        """Return if thumbnail should be sent to MQTT."""
        return self._send_to_mqtt


class RecorderConfig:
    """Recorder config."""

    schema = SCHEMA

    def __init__(self, recorder):
        self._lookback = recorder["lookback"]
        self._timeout = recorder["timeout"]
        self._retain = recorder["retain"]
        self._folder = recorder["folder"]
        self._filename_pattern = recorder["filename_pattern"]
        self._extension = recorder["extension"]
        self._hwaccel_args = recorder["hwaccel_args"]
        self._codec = recorder["codec"]
        self._audio_codec = recorder["audio_codec"]
        self._filter_args = recorder["filter_args"]
        self._segments_folder = recorder["segments_folder"]
        self._thumbnail = Thumbnail(recorder["thumbnail"])

    @property
    def lookback(self):
        """Return lookback."""
        return self._lookback

    @property
    def timeout(self):
        """Return timeout."""
        return self._timeout

    @property
    def retain(self):
        """Return days to retain."""
        return self._retain

    @property
    def folder(self):
        """Return folder where recordings are stored."""
        return self._folder

    @property
    def filename_pattern(self):
        """Return filename strftime pattern."""
        return self._filename_pattern

    @property
    def extension(self):
        """Return recording file extension."""
        return self._extension

    @property
    def hwaccel_args(self):
        """Return FFmpeg hwaccel args."""
        return self._hwaccel_args

    @property
    def codec(self):
        """Return codec for FFmpeg command."""
        return ["-c:v", self._codec]

    @property
    def audio_codec(self):
        """Return audio codec for FFmpeg command."""
        return ["-c:a", self._audio_codec]

    @property
    def filter_args(self):
        """Return FFmpeg filter args."""
        return self._filter_args

    @property
    def segments_folder(self):
        """Return folder where segments are stored."""
        return self._segments_folder

    @property
    def thumbnail(self):
        """Return thumbnail config."""
        return self._thumbnail
