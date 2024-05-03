"""A dictionary with a fixed size.

If the dictionary exceeds the maximum size, the oldest item is removed.
"""
from __future__ import annotations

import typing
from collections import OrderedDict
from collections.abc import MutableMapping

_KT = typing.TypeVar("_KT")
_VT = typing.TypeVar("_VT")


class FixedSizeDict(OrderedDict, MutableMapping[_KT, _VT]):
    """A dictionary with a fixed size.

    If the dictionary exceeds the maximum size, the oldest item is removed.
    Each time an item is accessed it is moved to the end of the dictionary.
    """

    def __init__(self, *args, maxlen=0, **kwargs):
        self._maxlen = maxlen
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value) -> None:
        """Set an item in the dictionary.

        Deleting the oldest item if the dictionary exceeds the maximum size.
        """
        super().__setitem__(key, value)
        if self._maxlen > 0:
            if len(self) > self._maxlen:
                self.pop(next(iter(self)))

    def get(self, key: _KT, *arg) -> _VT | None:
        """Get an item from the dictionary.

        Move the item to the end of the dictionary so that it is not removed.
        """
        if key in self:
            self.move_to_end(key)
        return super().get(key, *arg)
