"""Viseron domains."""
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from viseron.const import LOADING
from viseron.domain_registry import DomainEntry, DomainState

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.types import SupportedDomains


LOGGER = logging.getLogger(__name__)


@dataclass
class RequireDomain:
    """Mark domain with given identifier as a required dependency.

    Viseron will make sure that all required domains are resolved before setting up
    the domain.
    """

    domain: SupportedDomains
    identifier: str


class OptionalDomain(RequireDomain):
    """Mark domain with given identifier as a optional dependency.

    If the optional domain is marked for setup, it will be awaited before setting up
    the domain.
    If the optional domain is NOT marked for setup, Viseron will ignore the dependency.
    """


class DomainMeta(ABCMeta):
    """Metaclass for domains.

    This metaclass will call __post_init__ after __init__ in order to register
    domains without explicitly doing so in __init__.
    """

    def __call__(cls, *args, **kwargs):
        """Call __post_init__ after __init__."""
        instance = super().__call__(*args, **kwargs)
        if hasattr(instance, "__post_init__"):
            instance.__post_init__(*args, **kwargs)
            return instance
        raise NotImplementedError(f"Class {cls} must implement __post_init__")


class AbstractDomain(metaclass=DomainMeta):
    """Abstract domain class."""

    @abstractmethod
    def __post_init__(self, *args, **kwargs):
        """Post init, called automatically after __init__."""


def setup_domain(
    vis: Viseron,
    component: str,
    domain: SupportedDomains,
    config: dict[str, Any],
    identifier: str,
    require_domains: list[RequireDomain] | None = None,
    optional_domains: list[OptionalDomain] | None = None,
) -> None:
    """Set up single domain."""
    component_instance = vis.data[LOADING][component]
    component_instance.add_domain_to_setup(
        domain, config, identifier, require_domains, optional_domains
    )


def get_unload_order(
    vis: Viseron, domain: SupportedDomains, identifier: str
) -> list[DomainEntry]:
    """Get domains in unload order (dependents first)."""
    registry = vis.domain_registry
    unload_order: list[DomainEntry] = []
    processed: set[tuple[SupportedDomains, str]] = set()

    def traverse(_domain: SupportedDomains, _identifier: str) -> None:
        key = (_domain, _identifier)
        if key in processed:
            return
        processed.add(key)

        # Process dependents first
        for dep in registry.get_dependents(_domain, _identifier):
            traverse(dep.domain, dep.identifier)

        # Then add this domain
        entry = registry.get(_domain, _identifier)
        if entry and entry.state == DomainState.LOADED:
            unload_order.append(entry)

    traverse(domain, identifier)
    return unload_order


def unload_domain(
    vis: Viseron,
    domain: SupportedDomains,
    identifier: str,
) -> DomainEntry | None:
    """Unload a single domain."""
    registry = vis.domain_registry
    entry = registry.get(domain, identifier)

    if not entry or entry.state != DomainState.LOADED:
        LOGGER.error(
            f"Domain {domain} with identifier {identifier} not loaded, cannot unload"
        )
        return None

    LOGGER.info(f"Unloading domain {domain} with identifier {identifier}")

    # Unload entities for this domain
    component_name = entry.component_name
    entities_to_remove: list[str] = []
    entity_owner = vis.states.entity_owner.get(component_name)
    domains = entity_owner.get("domains") if entity_owner else None
    domain_info = domains.get(domain) if domains else None
    identifiers = domain_info.get("identifiers") if domain_info else None
    entities_to_remove = identifiers.get(identifier, []) if identifiers else []

    for entity_id in entities_to_remove:
        vis.states.unload_entity(entity_id)

    # Call domain's unload method
    if entry.instance and hasattr(entry.instance, "unload"):
        try:
            entry.instance.unload()
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.error(
                f"Error unloading domain {domain} with identifier {identifier}: {ex}"
            )
    else:
        LOGGER.debug(
            f"Domain {domain} with identifier {identifier} has no unload method"
        )

    # Unregister from registry
    return registry.unregister(domain, identifier)
