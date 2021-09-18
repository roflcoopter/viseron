"""Test config."""
import os
import sys
from contextlib import nullcontext
from unittest.mock import patch

import pytest
import voluptuous

from viseron.config import (
    NVRConfig,
    ViseronConfig,
    create_default_config,
    detector_enabled_check,
    import_motion_detection,
    load_config,
    load_secrets,
    motion_type_check,
)
from viseron.const import CONFIG_PATH, SECRETS_PATH
from viseron.exceptions import (
    MotionConfigError,
    MotionConfigSchemaError,
    MotionImportError,
    MotionModuleNotFoundError,
)

from tests.common import assert_config_instance_config_dict
from tests.motion import (
    config_embedded,
    config_module_does_not_inherit,
    config_module_missing,
    config_module_schema_missing,
    config_separate,
    does_not_have_motion_class,
    does_not_inherit,
)


def teardown():
    """Clean up."""
    if os.path.isfile(CONFIG_PATH):
        os.remove(CONFIG_PATH)
    if os.path.isfile(SECRETS_PATH):
        os.remove(SECRETS_PATH)


def test_detector_enabled_check():
    """Test that detector can't be enabled per camera if disabled globally."""
    config = {
        "object_detection": {
            "enable": False,
        },
        "cameras": [
            {
                "name": "Test camera",
                "object_detection": {
                    "enable": True,
                },
            }
        ],
    }
    with pytest.raises(voluptuous.error.Invalid):
        detector_enabled_check(config)


def test_motion_type_check():
    """Test that local motion detection type can't differ from global."""
    config = {
        "motion_detection": {
            "type": "background_subtractor",
        },
        "cameras": [
            {
                "name": "Test camera",
                "motion_detection": {
                    "type": "other",
                },
            }
        ],
    }
    with pytest.raises(voluptuous.error.Invalid):
        motion_type_check(config)


@pytest.mark.parametrize(
    "config, motion_module, raises",
    [
        ({"type": "config_embedded"}, config_embedded, nullcontext()),
        ({"type": "config_separate"}, config_separate, nullcontext()),
        (
            {"type": "does_not_exist"},
            None,
            pytest.raises(MotionModuleNotFoundError),
        ),
        (
            {"type": "does_not_have_motion_class"},
            does_not_have_motion_class,
            pytest.raises(MotionImportError),
        ),
        (
            {"type": "does_not_inherit"},
            does_not_inherit,
            pytest.raises(MotionImportError),
        ),
        (
            {"type": "config_module_missing"},
            config_module_missing,
            pytest.raises(MotionConfigError),
        ),
        (
            {"type": "config_module_does_not_inherit"},
            config_module_does_not_inherit,
            pytest.raises(MotionConfigError),
        ),
        (
            {"type": "config_module_schema_missing"},
            config_module_schema_missing,
            pytest.raises(MotionConfigSchemaError),
        ),
    ],
)
def test_import_motion_detection(config, motion_module, raises):
    """Test that dynamic import works."""
    if motion_module:
        sys.modules[f"viseron.motion.{config['type']}"] = motion_module

    with raises:
        import_motion_detection(config)


@patch("viseron.config.CONFIG_PATH", "")
def test_create_default_config_returns_false_if_write_error():
    """Test that default config is created."""
    result = create_default_config()
    assert result is False


def test_load_config(simple_config):
    """Test loading of config from file."""
    with open(CONFIG_PATH, "wt") as config_file:
        config_file.write(simple_config)
    load_config()


def test_load_config_missing():
    """Test load config file when file is missing."""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        load_config()
    assert pytest_wrapped_e.type == SystemExit
    assert os.path.isfile(CONFIG_PATH)


def test_load_config_secret(simple_config_secret):
    """Test load config with secrets."""
    with open(CONFIG_PATH, "wt") as config_file:
        config_file.write(simple_config_secret)
    with open(SECRETS_PATH, "w") as secrets_file:
        secrets_file.write("port: 554")
    load_config()


def test_load_config_secret_file_missing(simple_config_secret):
    """Test load config when secrets file is missing."""
    with open(CONFIG_PATH, "wt") as config_file:
        config_file.write(simple_config_secret)
    with pytest.raises(ValueError):
        load_config()


def test_load_config_secret_node_missing(simple_config_secret):
    """Test load config with undefined secret."""
    with open(CONFIG_PATH, "wt") as config_file:
        config_file.write(simple_config_secret)
    with open(SECRETS_PATH, "w") as secrets_file:
        secrets_file.write("test: abc")
    with pytest.raises(ValueError):
        load_config()


def test_load_secrets():
    """Test load secrets file.."""
    with open(SECRETS_PATH, "w") as secrets_file:
        secrets_file.write("test: abc")
    secrets = load_secrets()
    assert secrets == {"test": "abc"}


@pytest.mark.usefixtures("raw_config_full")
class TestViseronConfig:
    """Tests for ViseronConfig."""

    def test_init(self, raw_config):
        """Test __init__ method."""
        config = ViseronConfig(raw_config)
        assert_config_instance_config_dict(
            config, raw_config, ignore_keys=["codec", "audio_codec"]
        )


GLOBAL_MOTION_DETECTION = {
    "type": "background_subtractor",
    "threshold": 15,
    "height": 300,
    "trigger_recorder": False,
    "width": 300,
    "interval": 1.0,
    "frames": 3,
    "alpha": 0.1,
    "max_timeout": 30,
    "area": 0.08,
    "trigger_detector": True,
    "mask": [],
    "timeout": True,
}

LOCAL_MOTION_DETECTION = {
    "type": "background_subtractor",
    "threshold": 15,
    "height": 300,
    "trigger_recorder": False,
    "width": 300,
    "interval": 1.0,
    "frames": 3,
    "alpha": 0.1,
    "max_timeout": 30,
    "area": 0.08,
    "trigger_detector": True,
    "mask": [],
    "timeout": True,
}


@pytest.mark.usefixtures("viseron_config")
class TestNVRConfig:
    """Tests for NVRConfig."""

    def test_init(self, viseron_config):
        """Test __init__ method."""
        config = NVRConfig(
            viseron_config.cameras[0],
            viseron_config.object_detection,
            viseron_config.motion_detection,
            viseron_config.recorder,
            viseron_config.mqtt,
            viseron_config.logging,
        )
        assert_config_instance_config_dict(
            config.camera,
            viseron_config.cameras[0],
            ignore_keys=["codec", "input_args"],
        )

    @pytest.mark.parametrize(
        "global_motion_detection, local_motion_detection, expected_config",
        [
            (GLOBAL_MOTION_DETECTION, {}, GLOBAL_MOTION_DETECTION),
            (
                GLOBAL_MOTION_DETECTION,
                LOCAL_MOTION_DETECTION,
                LOCAL_MOTION_DETECTION,
            ),
        ],
    )
    def test_values_overridden_motion(
        self,
        viseron_config,
        global_motion_detection,
        local_motion_detection,
        expected_config,
    ):
        """Test that local values override global values for motion."""
        viseron_config.cameras[0]["motion_detection"] = local_motion_detection
        viseron_config._motion_detection = global_motion_detection
        config = NVRConfig(
            viseron_config.cameras[0],
            viseron_config.object_detection,
            viseron_config.motion_detection,
            viseron_config.recorder,
            viseron_config.mqtt,
            viseron_config.logging,
        )
        assert_config_instance_config_dict(
            config.motion_detection,
            expected_config,
        )
