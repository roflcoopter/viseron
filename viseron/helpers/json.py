"""JSON helpers."""
import dataclasses
import datetime
import json
from enum import Enum
from typing import Any


class JSONEncoder(json.JSONEncoder):
    """Helper to convert objects to JSON."""

    def default(self, o: Any) -> Any:
        """Convert objects."""
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        if hasattr(o, "as_dict"):
            return o.as_dict()
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, datetime.timedelta):
            return int(o.total_seconds())
        if isinstance(o, Enum):
            return o.value

        return json.JSONEncoder.default(self, o)
