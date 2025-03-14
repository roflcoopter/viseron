"""JSON helpers."""
import dataclasses
import datetime
import json
from enum import Enum
from typing import Any

import numpy as np


class JSONEncoder(json.JSONEncoder):
    """Helper to convert objects to JSON."""

    def default(self, o: Any) -> Any:
        """Convert objects."""
        if isinstance(o, datetime.datetime):
            return o.replace(tzinfo=datetime.timezone.utc).isoformat()
        if hasattr(o, "as_dict"):
            return o.as_dict()
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)  # type: ignore[arg-type]
        if isinstance(o, datetime.timedelta):
            return int(o.total_seconds())
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, np.ndarray):
            return o.tolist()

        return json.JSONEncoder.default(self, o)
