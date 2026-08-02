"""Types for the fastalpr component."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from fast_alpr import ALPR


class FastAlprViseronData(TypedDict, total=False):
    """TypedDict for fastalpr Viseron data."""

    lock: threading.Lock
    instances: dict[tuple[str, float, str, str], ALPR]
