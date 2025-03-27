"""NVR component."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from viseron.domains import OptionalDomain, RequireDomain, setup_domain
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict
from viseron.types import Domain

from .const import CAMERA, COMPONENT, DESC_COMPONENT, DOMAIN

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): {
            CameraIdentifier(): vol.All(CoerceNoneToDict(), {}),
        }
    },
    extra=vol.ALLOW_EXTRA,
)


def optional_domains(identifier: str) -> list[OptionalDomain]:
    """Mark all domains as optional."""
    _optional_domains = []
    for domain in Domain:
        if domain not in (Domain.NVR, Domain.CAMERA):
            _optional_domains.append(
                OptionalDomain(domain=domain.value, identifier=identifier)
            )
    return _optional_domains


def setup(
    vis: Viseron,
    config: dict[str, Any],
) -> bool:
    """Set up the nvr component."""
    config = config[COMPONENT]

    for camera_identifier in config.keys():
        setup_domain(
            vis,
            COMPONENT,
            DOMAIN,
            config,
            identifier=camera_identifier,
            require_domains=[
                RequireDomain(
                    domain=CAMERA,
                    identifier=camera_identifier,
                )
            ],
            optional_domains=optional_domains(camera_identifier),
        )
    return True
