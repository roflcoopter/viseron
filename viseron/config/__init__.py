"""Create base configs for Viseron."""
import importlib
import sys

import yaml
from voluptuous import ALLOW_EXTRA, All, Any, Extra, Invalid, Optional, Required, Schema

from viseron.config.config_camera import CameraConfig
from viseron.const import CONFIG_PATH, DEFAULT_CONFIG, SECRETS_PATH
from viseron.exceptions import (
    MotionConfigError,
    MotionConfigSchemaError,
    MotionImportError,
    MotionModuleNotFoundError,
)
from viseron.motion import AbstractMotionDetection, AbstractMotionDetectionConfig

from .config_motion_detection import MotionDetectionConfig
from .config_mqtt import MQTTConfig
from .config_object_detection import ObjectDetectionConfig
from .config_post_processors import PostProcessorsConfig
from .config_recorder import RecorderConfig


def detector_enabled_check(config):
    """Check if detector is disabled globally but enabled locally for a camera."""
    if not config["object_detection"]["enable"]:
        for camera in config["cameras"]:
            if (
                camera.get("object_detection")
                and camera["object_detection"].get("enable")
                and camera["object_detection"]["enable"]
            ):
                raise Invalid(
                    f"You have disabled object detection globally, "
                    f"but have enabled object detection for camera {camera['name']}. "
                    "This is not supported."
                )
    return config


def motion_type_check(config):
    """Check if local motion detection type differs from global."""
    for camera in config["cameras"]:
        if (
            camera.get("motion_detection")
            and camera["motion_detection"].get("type")
            and camera["motion_detection"]["type"] != config["motion_detection"]["type"]
        ):
            raise Invalid(
                f"Motion detection type for camera {camera['name']} differs from "
                "the global config. This is not supported"
            )
    return config


def get_motion_type(motion_detection_config):
    """Set default type if it is missing."""
    if not motion_detection_config.get("type"):
        motion_detection_config["type"] = "background_subtractor"
    return motion_detection_config


def import_motion_detection(motion_detection_config):
    """Dynamically import schema for configured motion detector."""

    try:
        motion_module = importlib.import_module(
            "viseron.motion." + motion_detection_config["type"]
        )
    except ModuleNotFoundError as error:
        raise MotionModuleNotFoundError(motion_detection_config["type"]) from error

    if hasattr(motion_module, "MotionDetection") and issubclass(
        motion_module.MotionDetection, AbstractMotionDetection
    ):
        pass
    else:
        raise MotionImportError(motion_detection_config["type"])

    motion_config_module = None
    try:
        motion_config_module = importlib.import_module(
            "viseron.motion." + motion_detection_config["type"] + ".config"
        )
    except ModuleNotFoundError:
        pass

    config_module = motion_config_module if motion_config_module else motion_module
    if hasattr(config_module, "Config") and issubclass(
        config_module.Config, AbstractMotionDetectionConfig
    ):
        pass
    else:
        raise MotionConfigError(motion_detection_config["type"])

    if not hasattr(config_module, "SCHEMA"):
        raise MotionConfigSchemaError(motion_detection_config["type"])

    return config_module.Config, config_module.SCHEMA


def validate_motion_detection_schema(motion_detection_config):
    """Validate motion detection against dynamically imported schema."""
    _, schema = import_motion_detection(motion_detection_config)
    return schema(motion_detection_config)


VISERON_CONFIG_SCHEMA = Schema(
    All(
        {
            Required("cameras"): [{Extra: object}],
            Optional("object_detection", default={}): ObjectDetectionConfig.schema,
            Optional("motion_detection", default={}): All(
                get_motion_type, validate_motion_detection_schema
            ),
            Optional("post_processors", default={}): PostProcessorsConfig.schema,
            Optional("recorder", default={}): RecorderConfig.schema,
            Optional("mqtt", default=None): Any(MQTTConfig.schema, None),
        },
        detector_enabled_check,
        motion_type_check,
    ),
    extra=ALLOW_EXTRA,
)


class BaseConfig:
    """Contains config properties common for Viseron and each NVR thread."""

    def __init__(self):
        self._object_detection = None
        self._motion_detection = None
        self._post_processors = None
        self._recorder = None
        self._mqtt = None

    @property
    def object_detection(self) -> ObjectDetectionConfig:
        """Return object detection config."""
        return self._object_detection

    @property
    def motion_detection(self) -> MotionDetectionConfig:
        """Return motion detection config."""
        return self._motion_detection

    @property
    def post_processors(self) -> PostProcessorsConfig:
        """Return post processors config."""
        return self._post_processors

    @property
    def recorder(self) -> RecorderConfig:
        """Return recorder config."""
        return self._recorder

    @property
    def mqtt(self) -> MQTTConfig:
        """Return MQTT config."""
        return self._mqtt


class ViseronConfig(BaseConfig):
    """Config Viseron specifically."""

    raw_config = {}
    config = None

    def __init__(self, config):
        super().__init__()
        ViseronConfig.raw_config = config
        self._cameras = config["cameras"]
        self._object_detection = config["object_detection"]
        self._motion_detection = config["motion_detection"]
        self._post_processors = PostProcessorsConfig(config["post_processors"])
        self._recorder = RecorderConfig(config["recorder"])
        self._mqtt = MQTTConfig(config["mqtt"]) if config.get("mqtt", None) else None
        ViseronConfig.config = self

    @property
    def cameras(self) -> dict:
        """Return cameras config."""
        return self._cameras


class NVRConfig(BaseConfig):
    """Config that is created for each NVR instance, eg one per camera."""

    def __init__(self, camera, object_detection, motion_detection, recorder, mqtt):
        super().__init__()
        self._camera = CameraConfig(camera, motion_detection)
        self._object_detection = ObjectDetectionConfig(
            object_detection, self._camera.object_detection, self._camera.zones
        )

        # Override global values with local values
        motion_detection_config_class, _ = import_motion_detection(motion_detection)
        self._motion_detection = motion_detection_config_class(
            self._camera.motion_detection
        )

        self._recorder = recorder
        self._mqtt = mqtt

    @property
    def camera(self) -> CameraConfig:
        """Return camera config."""
        return self._camera


def create_default_config():
    """Create default configuration."""
    try:
        with open(CONFIG_PATH, "wt", encoding="utf-8") as config_file:
            config_file.write(DEFAULT_CONFIG)
    except OSError:
        print("Unable to create default configuration file", CONFIG_PATH)
        return False
    return True


def load_secrets():
    """Return secrets from secrets.yaml."""
    try:
        with open(SECRETS_PATH, "r", encoding="utf-8") as secrets_file:
            return yaml.load(secrets_file, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        return None


def load_config():
    """Return contents of config.yaml."""
    secrets = load_secrets()

    def secret_yaml(_, node):
        if secrets is None:
            raise ValueError(
                "!secret found in config.yaml, but no secrets.yaml exists. "
                f"Make sure it exists under {SECRETS_PATH}"
            )
        if node.value not in secrets:
            raise ValueError(f"secret {node.value} does not exist in secrets.yaml")
        return secrets[node.value]

    yaml.add_constructor("!secret", secret_yaml, Loader=yaml.SafeLoader)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
            raw_config = yaml.load(config_file, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        print(
            f"Unable to find configuration. Creating default one in {CONFIG_PATH}\n"
            f"Please fill in the necessary configuration options and restart Viseron"
        )
        create_default_config()
        sys.exit()
    return raw_config
