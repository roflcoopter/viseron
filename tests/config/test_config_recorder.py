"""Tests for recorder config."""
from viseron.config import config_recorder

from tests.helpers import assert_config_instance_config_dict

RECORDER_CONFIG = config_recorder.SCHEMA(
    {
        "thumbnail": {
            "save_to_disk": False,
            "send_to_mqtt": False,
        },
        "lookback": 5,
        "folder": "/recordings",
        "extension": "mp4",
        "segments_folder": "/segments",
        "audio_codec": "aac",
        "timeout": 10,
        "retain": 7,
        "hwaccel_args": [],
        "codec": "copy",
        "filter_args": [],
        "logging": {
            "level": "debug",
        },
    }
)


class TestRecorderConfig:
    """Test RecorderConfig."""

    def test_init(self):
        """Test instantiation."""
        config = config_recorder.RecorderConfig(RECORDER_CONFIG)
        assert_config_instance_config_dict(
            config, RECORDER_CONFIG, ignore_keys=["codec", "audio_codec"]
        )
        assert config.codec == [
            "-c:v",
            RECORDER_CONFIG["codec"],
        ]
        assert config.audio_codec == [
            "-c:a",
            RECORDER_CONFIG["audio_codec"],
        ]
