"""JSON helpers."""
import dataclasses
import datetime
import json
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

        return json.JSONEncoder.default(self, o)
