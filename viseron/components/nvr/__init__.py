"""NVR component."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol

from viseron.const import DOMAIN_IDENTIFIERS
from viseron.domains import RequireDomain, setup_domain
from viseron.helpers.validators import ensure_slug, none_to_dict

from .const import CAMERA, COMPONENT, DOMAIN, MOTION_DETECTOR, OBJECT_DETECTOR

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.All(str, ensure_slug): vol.All(None, none_to_dict),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the nvr component."""
    config = config[COMPONENT]

    for camera_identifier in config.keys():
        require_domains = []
        require_domains.append(
            RequireDomain(
                domain=CAMERA,
                identifier=camera_identifier,
            )
        )
        if (
            OBJECT_DETECTOR in vis.data[DOMAIN_IDENTIFIERS]
            and camera_identifier in vis.data[DOMAIN_IDENTIFIERS][OBJECT_DETECTOR]
        ):
            require_domains.append(
                RequireDomain(
                    domain=OBJECT_DETECTOR,
                    identifier=camera_identifier,
                )
            )
        if (
            MOTION_DETECTOR in vis.data[DOMAIN_IDENTIFIERS]
            and camera_identifier in vis.data[DOMAIN_IDENTIFIERS][MOTION_DETECTOR]
        ):
            require_domains.append(
                RequireDomain(
                    domain=MOTION_DETECTOR,
                    identifier=camera_identifier,
                )
            )

        setup_domain(
            vis,
            COMPONENT,
            DOMAIN,
            config,
            identifier=camera_identifier,
            require_domains=require_domains,
        )
    return True
