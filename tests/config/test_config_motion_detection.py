"""Tests for motion detection config."""
import numpy as np
import pytest

from viseron.config import config_motion_detection

from tests.helpers import assert_config_instance_config_dict

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

MASK_COORDINATES = [
    {
        "points": [
            {"x": 0, "y": 0},
            {"x": 250, "y": 0},
            {"x": 250, "y": 250},
            {"x": 0, "y": 250},
        ],
    },
    {
        "points": [
            {"x": 500, "y": 500},
            {"x": 1000, "y": 500},
            {"x": 1000, "y": 750},
            {"x": 300, "y": 750},
        ],
    },
]

MASK_ARRAY = [
    np.array([[0, 0], [250, 0], [250, 250], [0, 250]]),
    np.array([[500, 500], [1000, 500], [1000, 750], [300, 750]]),
]


class TestMotionDetectionConfig:
    """Test MotionDetectionCOnfig."""

    @pytest.fixture
    def config(self, raw_config_full):
        """Return a config with motion_detection attribute."""
        raw_config_full["cameras"][0][
            "motion_detection"
        ] = CAMERA_MOTION_DETECTION_CONFIG
        raw_config_full["cameras"][0]["motion_detection"]["mask"] = MASK_COORDINATES
        return config_motion_detection.MotionDetectionConfig(
            raw_config_full["motion_detection"],
            raw_config_full["cameras"][0]["motion_detection"],
        )

    def test_generate_mask(self, config):
        """Test that mask is generated properly."""
        np.testing.assert_array_equal(
            config.generate_mask(MASK_COORDINATES),
            MASK_ARRAY,
        )
        np.testing.assert_array_equal(
            config.mask,
            MASK_ARRAY,
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
