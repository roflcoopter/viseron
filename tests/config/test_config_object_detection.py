"""Tests for object detectiob config."""
from contextlib import nullcontext

import pytest
import voluptuous

from viseron.config import config_object_detection

from tests.helpers import assert_config_instance_config_dict

OBJECT_DETECTION_CONFIG = {
    "type": "darknet",
    "interval": 1,
    "labels": [
        {
            "label": "dog",
            "confidence": 0.5,
            "height_min": 0.5,
            "height_max": 0.5,
            "width_min": 0.5,
            "width_max": 0.5,
            "triggers_recording": True,
            "require_motion": True,
            "post_processor": "face_recognition",
        }
    ],
    "log_all_objects": True,
    "logging": {
        "level": "debug",
    },
}
CAMERA_OBJECT_DETECTION_CONFIG = {
    "type": "edgetpu",
    "interval": 2,
    "labels": [
        {
            "label": "cat",
            "confidence": 0.7,
            "height_min": 0.7,
            "height_max": 0.7,
            "width_min": 0.7,
            "width_max": 0.7,
            "triggers_recording": False,
            "require_motion": False,
            "post_processor": "",
        }
    ],
    "log_all_objects": False,
    "logging": {
        "level": "fatal",
    },
}

CAMERA_ZONES_CONFIG = [
    {
        "name": "zone1",
        "labels": [
            config_object_detection.LabelConfig(
                {
                    "label": "zone_cat",
                    "confidence": 0.1,
                    "height_min": 0.7,
                    "height_max": 0.7,
                    "width_min": 0.7,
                    "width_max": 0.7,
                    "triggers_recording": False,
                    "require_motion": False,
                    "post_processor": "",
                }
            )
        ],
    }
]


@pytest.mark.parametrize(
    "label, raises",
    [
        (
            {"height_min": 0, "height_max": 0, "width_min": 0, "width_max": 0},
            pytest.raises(voluptuous.error.Invalid),
        ),
        (
            {"height_min": 1, "height_max": 0, "width_min": 0, "width_max": 0},
            pytest.raises(voluptuous.error.Invalid),
        ),
        (
            {"height_min": 0, "height_max": 1, "width_min": 0, "width_max": 0},
            pytest.raises(voluptuous.error.Invalid),
        ),
        (
            {"height_min": 0, "height_max": 1, "width_min": 1, "width_max": 0},
            pytest.raises(voluptuous.error.Invalid),
        ),
        (
            {"height_min": 0, "height_max": 1, "width_min": 0, "width_max": 1},
            nullcontext(),
        ),
    ],
)
def test_ensure_min_max(label, raises):
    with raises:
        assert config_object_detection.ensure_min_max(label) == label


@pytest.mark.parametrize(
    "env_var, env_var_value, expected",
    [
        ("VISERON_CUDA_SUPPORTED", "true", "darknet"),
        ("VISERON_OPENCL_SUPPORTED", "true", "darknet"),
        ("VISERON_RASPBERRYPI3", "true", "edgetpu"),
        ("VISERON_RASPBERRYPI4", "true", "edgetpu"),
        ("", "", "darknet"),
    ],
)
def test_get_detector_type(monkeypatch, env_var, env_var_value, expected):
    if env_var:
        monkeypatch.setenv(env_var, env_var_value)
    assert config_object_detection.get_detector_type() == expected


class TestObjectDetectionConfig:
    """Test ObjectDetectionConfig."""

    @pytest.mark.parametrize(
        "object_detection, camera_object_detection, expected_config",
        [
            (OBJECT_DETECTION_CONFIG, {}, OBJECT_DETECTION_CONFIG),
            (
                OBJECT_DETECTION_CONFIG,
                CAMERA_OBJECT_DETECTION_CONFIG,
                CAMERA_OBJECT_DETECTION_CONFIG,
            ),
        ],
    )
    def test_values_overridden(
        self,
        object_detection,
        camera_object_detection,
        expected_config,
    ):
        """Test that camera values properly overrides global values."""
        config = config_object_detection.ObjectDetectionConfig(
            object_detection, camera_object_detection, CAMERA_ZONES_CONFIG
        )
        assert_config_instance_config_dict(
            config, expected_config, ignore_keys=["type"]
        )
        assert config.type == object_detection["type"]
        assert config.min_confidence == CAMERA_ZONES_CONFIG[0]["labels"][0].confidence
