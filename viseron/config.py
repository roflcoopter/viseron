"""Create base configs for Viseron."""
import logging

import yaml

from viseron.components.webserver.const import DEFAULT_PORT
from viseron.const import CONFIG_PATH, DEFAULT_CONFIG, SECRETS_PATH

LOGGER = logging.getLogger(__name__)


def create_default_config():
    """Create default configuration."""
    try:
        with open(CONFIG_PATH, "wt", encoding="utf-8") as config_file:
            config_file.write(DEFAULT_CONFIG)
    except OSError:
        LOGGER.error(
            f"Unable to create default configuration file in path {CONFIG_PATH}"
        )
        return False
    return True


def load_secrets():
    """Return secrets from secrets.yaml."""
    try:
        with open(SECRETS_PATH, "r", encoding="utf-8") as secrets_file:
            return yaml.load(secrets_file, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        return None


def load_config(create_default=True):
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
            yaml_config = yaml.load(config_file, Loader=yaml.SafeLoader)
            config_file.seek(0)
            raw_config = config_file.read()
    except FileNotFoundError as error:
        # Create default config and then load it
        if create_default:
            LOGGER.info(
                "Unable to find configuration. "
                f"Creating a default one in {CONFIG_PATH}. "
                f"Navigate to the Web UI running on port {DEFAULT_PORT} and fill it in"
            )
            create_default_config()
            return load_config(create_default=False)
        raise error

    # If we are loading the default config, treat it as an empty config
    if raw_config == DEFAULT_CONFIG:
        yaml_config = {}

    if yaml_config is None:
        yaml_config = {}

    # Convert values to dictionaries if they are None
    for key, value in yaml_config.items():
        yaml_config[key] = value or {}
    return yaml_config
