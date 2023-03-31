"""Viseron domains."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from viseron.const import LOADING

if TYPE_CHECKING:
    from viseron.components import Component
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


def setup_domain(
    vis,
    component,
    domain,
    config,
    identifier: str,
    require_domains: list[RequireDomain] | None = None,
    optional_domains: list[OptionalDomain] | None = None,
):
    """Set up single domain."""
    component_instance: Component = vis.data[LOADING][component]
    component_instance.add_domain_to_setup(
        domain, config, identifier, require_domains, optional_domains
    )
