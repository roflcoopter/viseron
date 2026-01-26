"""NVR domain."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.components.nvr.const import DOMAIN
from viseron.domains import AbstractDomain

if TYPE_CHECKING:
    from viseron import Viseron


class AbstractNVR(AbstractDomain):
    """Abstract NVR class."""

    def __init__(self, vis: Viseron, config, identifier: str) -> None:
        self._vis = vis
        self._camera_identifier = identifier
        self._config = config

    def __post_init__(self, *args, **kwargs):
        """Post init hook."""
        self._vis.register_domain(DOMAIN, self._camera_identifier, self)
