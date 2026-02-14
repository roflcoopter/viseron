"""Create base configs for Viseron."""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML

from viseron.const import CONFIG_PATH, DEFAULT_CONFIG, DEFAULT_PORT, SECRETS_PATH
from viseron.types import Domain

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


@dataclass
class DomainChange:
    """Represents a change to a domain configuration."""

    component_name: str
    domain: SupportedDomains
    old_config: dict[str, Any] | None
    new_config: dict[str, Any] | None
    identifier_changes: list[IdentifierChange] = field(default_factory=list)

    @property
    def is_added(self) -> bool:
        """Return True if this domain was added."""
        return self.old_config is None and self.new_config is not None

    @property
    def is_removed(self) -> bool:
        """Return True if this domain was removed."""
        return self.old_config is not None and self.new_config is None

    @property
    def is_domain_level_change(self) -> bool:
        """Return True if domain-level config changed."""
        if self.is_added or self.is_removed:
            return True

        if self.old_config is None or self.new_config is None:
            return False

        if self.domain == "camera":
            # For the camera domain, the identifiers are directly under the domain key,
            # and there are no domain-level settings.
            return False

        old_non_identifier_config = copy.deepcopy(self.old_config)
        new_non_identifier_config = copy.deepcopy(self.new_config)
        old_non_identifier_config.pop("cameras", None)
        new_non_identifier_config.pop("cameras", None)
        return old_non_identifier_config != new_non_identifier_config

    def get_identifier_configs(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return old and new identifier configurations as dictionaries.

        The camera domain is a special case where the identifiers are under the
        'camera' key directly and therefore the domain-level config is empty::
        ffmpeg:
          camera:
            camera1:
              host: ...

        For other domains, the identifiers are under the 'cameras' key:
        darknet:
          object_detector:
            some_object_detector_config: ...
            cameras:
              camera1:
                some_camera_specific_config: ...
        In this case, the domain-level config is everything except the 'cameras' key,
        and the identifier-level config is the contents of the 'cameras' key.
        """
        old_identifiers: dict[str, Any] = {}
        new_identifiers: dict[str, Any] = {}

        if self.old_config is not None:
            if self.domain == "camera":
                cameras = self.old_config
            else:
                cameras = self.old_config.get("cameras", {})
            for identifier in cameras:
                old_identifiers[identifier] = cameras[identifier]

        if self.new_config is not None:
            cameras = self.new_config.get("cameras", {})
            if self.domain == "camera":
                cameras = self.new_config
            else:
                cameras = self.new_config.get("cameras", {})
            for identifier in cameras:
                new_identifiers[identifier] = cameras[identifier]

        return old_identifiers, new_identifiers


@dataclass
class ComponentChange:
    """Represents a change to a component configuration."""

    component_name: str
    old_config: dict[str, Any] | None
    new_config: dict[str, Any] | None
    domain_changes: list[DomainChange] = field(default_factory=list)

    @property
    def is_added(self) -> bool:
        """Return True if this component was added."""
        return self.old_config is None and self.new_config is not None

    @property
    def is_removed(self) -> bool:
        """Return True if this component was removed."""
        return self.old_config is not None and self.new_config is None

    @property
    def is_component_level_change(self) -> bool:
        """Return True if component-level config changed (not just domains)."""
        if self.is_added or self.is_removed:
            return True

        if self.old_config is None or self.new_config is None:
            return False

        old_non_domain_config = copy.deepcopy(self.old_config)
        new_non_domain_config = copy.deepcopy(self.new_config)
        for domain in Domain:
            old_non_domain_config.pop(domain.value, None)
            new_non_domain_config.pop(domain.value, None)
        return old_non_domain_config != new_non_domain_config

    def get_domain_configs(
        self,
    ) -> tuple[dict[SupportedDomains, Any], dict[SupportedDomains, Any]]:
        """Return old and new domain configurations as dictionaries."""
        old_domains: dict[SupportedDomains, Any] = {}
        new_domains: dict[SupportedDomains, Any] = {}

        if self.old_config is not None:
            for domain in Domain:
                domain_value: SupportedDomains = domain.value
                if domain_value in self.old_config:
                    old_domains[domain_value] = self.old_config[domain_value]

        if self.new_config is not None:
            for domain in Domain:
                domain_value = domain.value
                if domain_value in self.new_config:
                    new_domains[domain_value] = self.new_config[domain_value]

        return old_domains, new_domains


@dataclass
class ConfigDiff:
    """Represents the difference between two configurations."""

    component_changes: dict[str, ComponentChange] = field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        """Return True if there are any changes."""
        return len(self.component_changes) > 0

    def get_added_components(self) -> list[str]:
        """Return list of added component names."""
        return [
            name for name, change in self.component_changes.items() if change.is_added
        ]

    def get_removed_components(self) -> list[str]:
        """Return list of removed component names."""
        return [
            name for name, change in self.component_changes.items() if change.is_removed
        ]

    def get_modified_components(self) -> list[str]:
        """Return list of component names with any changes (not added or removed)."""
        return [
            name
            for name, change in self.component_changes.items()
            if not change.is_added and not change.is_removed
        ]

    def get_component_change(self, component_name: str) -> ComponentChange | None:
        """Return the ComponentChange for a given component name."""
        return self.component_changes.get(component_name, None)


def diff_config(old_config: dict[str, Any], new_config: dict[str, Any]) -> ConfigDiff:
    """Compare two configurations and return the differences.

    Args:
        old_config: The previous configuration dictionary
        new_config: The new configuration dictionary

    Returns:
        ConfigDiff containing all changes between configurations
    """
    result = ConfigDiff()

    # Get all component names from both configs
    old_components = set(old_config.keys())
    new_components = set(new_config.keys())

    # Added components
    for component_name in new_components - old_components:
        result.component_changes[component_name] = ComponentChange(
            component_name=component_name,
            old_config=None,
            new_config=copy.deepcopy(new_config[component_name]),
        )

    # Removed components
    for component_name in old_components - new_components:
        result.component_changes[component_name] = ComponentChange(
            component_name=component_name,
            old_config=copy.deepcopy(old_config[component_name]),
            new_config=None,
        )

    # Modified components (present in both)
    for component_name in old_components & new_components:
        old_comp_config = old_config[component_name]
        new_comp_config = new_config[component_name]

        if old_comp_config != new_comp_config:
            result.component_changes[component_name] = ComponentChange(
                component_name=component_name,
                old_config=copy.deepcopy(old_comp_config),
                new_config=copy.deepcopy(new_comp_config),
            )

    return result


def diff_domain_config(
    component_name: str,
    old_config: dict[SupportedDomains, Any],
    new_config: dict[SupportedDomains, Any],
) -> list[DomainChange]:
    """Compare domain configurations within a component and return the differences.

    Args:
        old_config: The previous component configuration dictionary
        new_config: The new component configuration dictionary
        component_change: The ComponentChange object these domains belong to
    Returns:
        List of DomainChange containing all changes between domain configurations
    """
    result = []

    # Get all domain names from both configs
    old_domains = set(old_config.keys())
    new_domains = set(new_config.keys())

    # Added domains
    for domain_name in new_domains - old_domains:
        result.append(
            DomainChange(
                component_name=component_name,
                domain=domain_name,
                old_config=None,
                new_config=copy.deepcopy(new_config[domain_name]),
            )
        )

    # Removed domains
    for domain_name in old_domains - new_domains:
        result.append(
            DomainChange(
                component_name=component_name,
                domain=domain_name,
                old_config=copy.deepcopy(old_config[domain_name]),
                new_config=None,
            )
        )

    # Modified domains (present in both)
    for domain_name in old_domains & new_domains:
        old_domain_config = old_config[domain_name]
        new_domain_config = new_config[domain_name]

        if old_domain_config != new_domain_config:
            result.append(
                DomainChange(
                    component_name=component_name,
                    domain=domain_name,
                    old_config=copy.deepcopy(old_domain_config),
                    new_config=copy.deepcopy(new_domain_config),
                )
            )

    return result


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
