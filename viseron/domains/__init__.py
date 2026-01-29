"""Viseron domains."""
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from viseron.const import LOADING

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
    domain: str,
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
