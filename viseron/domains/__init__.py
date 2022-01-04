"""Viseron domains."""
import logging

from viseron.components import Component
from viseron.const import LOADING

LOGGER = logging.getLogger(__name__)


def setup_domain(vis, component, domain, config):
    """Set up single domain."""
    component_instance: Component = vis.data[LOADING][component]
    component_instance.add_domain_to_setup(domain, config)
