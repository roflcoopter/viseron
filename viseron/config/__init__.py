"""Create base configs for Viseron."""
import sys

import yaml
from voluptuous import All, Any, Invalid, Optional, Required, Schema

from viseron.const import CONFIG_PATH, DEFAULT_CONFIG, SECRETS_PATH

from .config_camera import CameraConfig
from .config_logging import LoggingConfig
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


VISERON_CONFIG_SCHEMA = Schema(
    All(
        {
            Required("cameras"): CameraConfig.schema,
            Optional("object_detection", default={}): ObjectDetectionConfig.schema,
            Optional(
                "motion_detection", default=MotionDetectionConfig.defaults
            ): MotionDetectionConfig.schema,
            Optional("post_processors", default={}): PostProcessorsConfig.schema,
            Optional("recorder", default={}): RecorderConfig.schema,
            Optional("mqtt", default=None): Any(MQTTConfig.schema, None),
            Optional("logging", default={}): LoggingConfig.schema,
        },
        detector_enabled_check,
    )
)


class BaseConfig:
    """Contains config properties common for Viseron and each NVR thread."""

    def __init__(self):
        self._object_detection = None
        self._motion_detection = None
        self._post_processors = None
        self._recorder = None
        self._mqtt = None
        self._logging = None

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

    @property
    def logging(self) -> LoggingConfig:
        """Return logging config."""
        return self._logging


class ViseronConfig(BaseConfig):
    """Config Viseron specifically."""

    def __init__(self, config):
        super().__init__()
        self._cameras = config["cameras"]
        self._object_detection = config["object_detection"]
        self._motion_detection = config["motion_detection"]
        self._post_processors = PostProcessorsConfig(config["post_processors"])
        self._recorder = RecorderConfig(config["recorder"])
        self._mqtt = MQTTConfig(config["mqtt"]) if config.get("mqtt", None) else None
        self._logging = LoggingConfig(config["logging"])

    @property
    def cameras(self) -> dict:
        """Return cameras config."""
        return self._cameras


class NVRConfig(BaseConfig):
    """Config that is created for each NVR instance, eg one per camera."""

    def __init__(
        self, camera, object_detection, motion_detection, recorder, mqtt, logging
    ):
        super().__init__()
        self._camera = CameraConfig(camera)
        self._object_detection = ObjectDetectionConfig(
            object_detection, self._camera.object_detection, self._camera.zones
        )
        self._motion_detection = MotionDetectionConfig(
            motion_detection,
            self._camera.motion_detection,
        )
        self._recorder = recorder
        self._mqtt = mqtt
        self._logging = logging

    @property
    def camera(self) -> CameraConfig:
        """Return camera config."""
        return self._camera


def create_default_config():
    """Create default configuration."""
    try:
        with open(CONFIG_PATH, "wt") as config_file:
            config_file.write(DEFAULT_CONFIG)
    except OSError:
        print("Unable to create default configuration file", CONFIG_PATH)
        return False
    return True


def load_secrets():
    """Return secrets from secrets.yaml."""
    try:
        with open(SECRETS_PATH, "r") as secrets_file:
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
        with open(CONFIG_PATH, "r") as config_file:
            raw_config = yaml.load(config_file, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        print(
            f"Unable to find configuration. Creating default one in {CONFIG_PATH}\n"
            f"Please fill in the necessary configuration options and restart Viseron"
        )
        create_default_config()
        sys.exit()
    return VISERON_CONFIG_SCHEMA(raw_config)
