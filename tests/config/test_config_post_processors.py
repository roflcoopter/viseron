"""Tests for post processors config."""
from viseron.config import config_post_processors

from tests.common import assert_config_instance_config_dict

POST_PROCESSORS_CONFIG = config_post_processors.SCHEMA(
    {
        "face_recognition": {
            "type": "dlib",
        },
        "logging": {
            "level": "debug",
        },
    }
)


class TestPostProcessorsConfig:
    """Test PostProcessorsConfig."""

    def test_init(self):
        """Test instantiation."""
        config = config_post_processors.PostProcessorsConfig(POST_PROCESSORS_CONFIG)
        assert_config_instance_config_dict(
            config, POST_PROCESSORS_CONFIG, ignore_keys=["type"]
        )
        post_processors_config = POST_PROCESSORS_CONFIG.copy()
        post_processors_config.pop("logging")
        assert config.post_processors == post_processors_config
