"""Create base configs for Viseron."""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML

from viseron.const import CONFIG_PATH, DEFAULT_CONFIG, DEFAULT_PORT, SECRETS_PATH

if TYPE_CHECKING:
    from viseron.types import SupportedDomains

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


@dataclass
class IdentifierChange:
    """Represents a change to a domain identifier configuration."""

    component_name: str
    domain: SupportedDomains
    identifier: str
    old_config: dict[str, Any] | None
    new_config: dict[str, Any] | None

    @property
    def is_added(self) -> bool:
        """Return True if this identifier was added."""
        return self.old_config is None and self.new_config is not None

    @property
    def is_removed(self) -> bool:
        """Return True if this identifier was removed."""
        return self.old_config is not None and self.new_config is None

    @property
    def is_identifier_level_change(self) -> bool:
        """Return True if identifier-level config changed."""
        if self.is_added or self.is_removed:
            return True

        if self.old_config is None or self.new_config is None:
            return False

        return self.old_config != self.new_config


def diff_identifier_config(
    component_name: str,
    domain: SupportedDomains,
    old_config: dict[str, Any],
    new_config: dict[str, Any],
) -> list[IdentifierChange]:
    """Compare identifier configurations within a domain and return the differences.

    Args:
        old_config: The previous domain configuration dictionary
        new_config: The new domain configuration dictionary
    Returns:
        List of IdentifierChange containing all changes between identifier configs
    """
    result = []

    old_identifiers = set(old_config.keys())
    new_identifiers = set(new_config.keys())

    # Added identifiers
    for identifier in new_identifiers - old_identifiers:
        result.append(
            IdentifierChange(
                component_name=component_name,
                domain=domain,
                identifier=identifier,
                old_config=None,
                new_config=copy.deepcopy(new_config[identifier]),
            )
        )

    # Removed identifiers
    for identifier in old_identifiers - new_identifiers:
        result.append(
            IdentifierChange(
                component_name=component_name,
                domain=domain,
                identifier=identifier,
                old_config=copy.deepcopy(old_config[identifier]),
                new_config=None,
            )
        )

    # Modified identifiers (present in both)
    for identifier in old_identifiers & new_identifiers:
        old_identifier_config = old_config[identifier]
        new_identifier_config = new_config[identifier]

        if old_identifier_config != new_identifier_config:
            result.append(
                IdentifierChange(
                    component_name=component_name,
                    domain=domain,
                    identifier=identifier,
                    old_config=copy.deepcopy(old_identifier_config),
                    new_config=copy.deepcopy(new_identifier_config),
                )
            )

    return result
