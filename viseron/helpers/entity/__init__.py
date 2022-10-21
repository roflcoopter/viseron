"""Base entity abstract class."""
from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from viseron import Viseron


class Entity(ABC):
    """Base entity class.

    entity_id will be generated with the help of 'domain'.'object_id'.
    If object_id is not set, it will be generated using name.
    name is the only required property.
    """

    # The following variables should NOT be overridden
    entity_id: str = None  # type:ignore
    vis: Viseron = None  # type:ignore
    domain: str = NotImplemented  # type:ignore

    # These are safe to override
    name: str = NotImplemented  # type:ignore
    object_id: str | None = None
    _state: Any = "unknown"
    _attributes: Dict[Any, Any] = {}

    # Used by Home Assistant, safe to override
    availability: List[Dict[str, str]] | None = None
    availability_mode: str = "all"
    device_name: str | None = None
    device_identifiers: List[str] | None = None
    enabled_by_default: bool = True
    entity_category: str | None = None
    icon: str | None = None

    @property
    def state(self):
        """Return entity state."""
        return self._state

    @property
    def json_serializable_state(self):
        """Return entity state that is json serializable."""
        return self.state

    @property
    def attributes(self):
        """Return entity attributes."""
        return self._attributes

    @property
    def json_serializable_attributes(self):
        """Return entity attributes that is json serializable."""
        return self.attributes

    def set_state(self):
        """Set the state in the states registry."""
        if self.vis is None:
            raise RuntimeError(f"Attribute vis has not been set for {self}")

        self.vis.states.set_state(self)

    def update(self):
        """Update entity."""
        raise NotImplementedError()
