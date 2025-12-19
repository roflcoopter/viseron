"""Create base configs for Viseron."""
import logging

from ruamel.yaml import YAML

from viseron.const import CONFIG_PATH, DEFAULT_CONFIG, DEFAULT_PORT, SECRETS_PATH

LOGGER = logging.getLogger(__name__)

UNSUPPORTED = object()


def create_default_config(config_path) -> bool:
    """Create default configuration."""
    try:
        with open(config_path, "w", encoding="utf-8") as config_file:
            config_file.write(DEFAULT_CONFIG)
    except OSError:
        LOGGER.error(
            f"Unable to create default configuration file in path {config_path}"
        )
        return False
    return True


def load_secrets():
    """Return secrets from secrets.yaml."""
    try:
        yaml = YAML(typ="safe", pure=True)
        with open(SECRETS_PATH, encoding="utf-8") as secrets_file:
            return yaml.load(secrets_file)
    except FileNotFoundError:
        return None


def load_config(create_default=True):
    """Return contents of config.yaml."""
    secrets = load_secrets()

    def secret_constructor(loader, node):
        if secrets is None:
            raise ValueError(
                "!secret found in config.yaml, but no secrets.yaml exists. "
                f"Make sure it exists under {SECRETS_PATH}"
            )
        value = loader.construct_scalar(node)
        if value not in secrets:
            raise ValueError(f"secret {value} does not exist in secrets.yaml")
        return secrets[value]

    yaml = YAML(typ="safe", pure=True)
    yaml.constructor.add_constructor("!secret", secret_constructor)

    try:
        with open(CONFIG_PATH, encoding="utf-8") as config_file:
            yaml_config = yaml.load(config_file)
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
            create_default_config(CONFIG_PATH)
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
