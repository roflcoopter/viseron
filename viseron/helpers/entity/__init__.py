"""Base entity abstract class."""

from abc import ABC
from typing import Any, Dict

from viseron import Viseron


class Entity(ABC):
    """Base entity class."""

    entity_id: str = None  # type:ignore
    vis: Viseron = None  # type:ignore

    entity_id_format: str = NotImplemented  # type:ignore
    _name: str = NotImplemented  # type:ignore

    _state: Any = "unknown"
    _attributes: Dict[Any, Any] = {}

    @property
    def state(self):
        """Return entity state."""
        return self._state

    @property
    def name(self):
        """Return entity name."""
        return self._name

    @property
    def attributes(self):
        """Return entity attributes."""
        return self._attributes

    def set_state(self):
        """Set the state in the states registry."""
        if self.vis is None:
            raise RuntimeError(f"Attribute vis has not been set for {self}")

        self.vis.states.set_state(self)
