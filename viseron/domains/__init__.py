"""Viseron domains."""
import logging

from viseron.components import Component
from viseron.const import LOADING

LOGGER = logging.getLogger(__name__)


def setup_domain(vis, config, component, domain):
    """Set up single component."""
    LOGGER.info(f"Setting up domain {domain} for component {component}")
    component_instance: Component = vis.data[LOADING][component]
    component_instance.setup_domain(config, domain)
