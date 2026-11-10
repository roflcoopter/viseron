"""NVR component."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from viseron.domains import OptionalDomain, RequireDomain, setup_domain
from viseron.helpers.config_model import ComponentRoot, ConfigModel
from viseron.helpers.config_types import CameraIdentifier, NoneToDict
from viseron.viseron_types import Domain

from .const import CAMERA, COMPONENT, DESC_COMPONENT, DOMAIN

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

class NVRConfig(ConfigModel):
    """Per-camera NVR configuration."""


class NVRRoot(ComponentRoot):
    """Config with the NVR component at the root."""

    nvr: dict[CameraIdentifier, Annotated[NVRConfig, NoneToDict]] = Field(
        min_length=1, description=DESC_COMPONENT
    )


CONFIG_SCHEMA = NVRRoot


def optional_domains(identifier: str) -> list[OptionalDomain]:
    """Mark all domains as optional."""
    _optional_domains = []
    for domain in Domain:
        if domain not in (Domain.NVR, Domain.CAMERA):
            _optional_domains.append(
                OptionalDomain(domain=domain.value, identifier=identifier)
            )
    return _optional_domains


def setup_domains(
    vis: Viseron,
    config: NVRRoot,
) -> None:
    """Set up nvr domains."""
    nvr_config = {
        camera_identifier: camera_config.model_dump()
        for camera_identifier, camera_config in config.nvr.items()
    }

    for camera_identifier in nvr_config:
        setup_domain(
            vis,
            COMPONENT,
            DOMAIN,
            nvr_config,
            identifier=camera_identifier,
            require_domains=[
                RequireDomain(
                    domain=CAMERA,
                    identifier=camera_identifier,
                )
            ],
            optional_domains=optional_domains(camera_identifier),
        )
