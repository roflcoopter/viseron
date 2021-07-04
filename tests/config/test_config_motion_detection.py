"""Tests for motion detection config."""
import pytest

from viseron.config import config_motion_detection

from tests.common import assert_config_instance_config_dict

MOTION_DETECTION_CONFIG = config_motion_detection.SCHEMA(
    {
        "interval": 1,
        "trigger_detector": True,
        "timeout": True,
        "max_timeout": 1,
        "width": 1,
        "height": 1,
        "area": 0.1,
        "threshold": 1,
        "alpha": 0.1,
        "frames": 1,
        "logging": {"level": "info"},
    }
)


CAMERA_MOTION_DETECTION_CONFIG = config_motion_detection.SCHEMA(
    {
        "interval": 2,
        "trigger_detector": False,
        "timeout": False,
        "max_timeout": 2,
        "width": 2,
        "height": 2,
        "area": 0.2,
        "threshold": 2,
        "alpha": 0.2,
        "frames": 2,
        "logging": {"level": "debug"},
    }
)


class TestMotionDetectionConfig:
    """Test MotionDetectionCOnfig."""

    @pytest.fixture
    def config(self, raw_config_full):
        """Return a config with motion_detection attribute."""
        raw_config_full["cameras"][0][
            "motion_detection"
        ] = CAMERA_MOTION_DETECTION_CONFIG
        return config_motion_detection.MotionDetectionConfig(
            raw_config_full["motion_detection"],
            raw_config_full["cameras"][0]["motion_detection"],
        )

    @pytest.mark.parametrize(
        "motion_detection, camera_motion_detection, expected_config",
        [
            (MOTION_DETECTION_CONFIG, {}, MOTION_DETECTION_CONFIG),
            (
                MOTION_DETECTION_CONFIG,
                CAMERA_MOTION_DETECTION_CONFIG,
                CAMERA_MOTION_DETECTION_CONFIG,
            ),
        ],
    )
    def test_values_overridden(
        self,
        motion_detection,
        camera_motion_detection,
        expected_config,
    ):
        """Test that camera values properly overrides global values."""
        config = config_motion_detection.MotionDetectionConfig(
            motion_detection, camera_motion_detection
        )
        assert_config_instance_config_dict(
            config, expected_config, ignore_keys=["mask"]
        )
