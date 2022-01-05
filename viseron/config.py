"""Create base configs for Viseron."""
import sys

import yaml

from viseron.const import CONFIG_PATH, DEFAULT_CONFIG, SECRETS_PATH


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

    # Convert values to dictionaries if they are None
    for key, value in raw_config.items():
        raw_config[key] = value or {}
    return raw_config
