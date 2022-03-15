"""Viseron domains."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

from viseron.const import LOADING

if TYPE_CHECKING:
    from viseron.components import Component
    from viseron.types import SupportedDomains


LOGGER = logging.getLogger(__name__)


@dataclass
class RequireDomain:
    """Require other domain with specific identifier to be setup before this one."""

    domain: SupportedDomains
    identifier: str


def setup_domain(
    vis,
    component,
    domain,
    config,
    identifier: str = None,
    require_domains: List[RequireDomain] | None = None,
):
    """Set up single domain."""
    component_instance: Component = vis.data[LOADING][component]
    component_instance.add_domain_to_setup(domain, config, identifier, require_domains)
