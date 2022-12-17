"""Detected object class."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from viseron.domains.camera.shared_frames import SharedFrame
from viseron.helpers import (
    calculate_absolute_coords,
    calculate_relative_coords,
    convert_letterboxed_bbox,
)


class DetectedObject:
    """Object that holds a detected object.

    All coordinates and metrics are relative to make it easier to do calculations on
    different image resolutions.
    """

    def __init__(
        self,
        label,
        confidence,
        x1,
        y1,
        x2,
        y2,
        relative=True,
        model_res=None,
        letterboxed=False,
        frame_res=None,
    ):
        self._label = label
        self._confidence = round(float(confidence), 3)

        if letterboxed:
            if relative:
                x1, y1, x2, y2 = calculate_absolute_coords((x1, y1, x2, y2), model_res)

            (x1, y1, x2, y2) = convert_letterboxed_bbox(
                frame_res[0],
                frame_res[1],
                model_res[0],
                model_res[1],
                (x1, y1, x2, y2),
            )
            # convert_letterboxed_bbox returns the bbox in frame_res based coordinates
            (x1, y1, x2, y2) = calculate_relative_coords((x1, y1, x2, y2), frame_res)
            relative = True

        if relative:
            self._rel_x1 = float(round(x1, 3))
            self._rel_y1 = float(round(y1, 3))
            self._rel_x2 = float(round(x2, 3))
            self._rel_y2 = float(round(y2, 3))
        else:
            (
                self._rel_x1,
                self._rel_y1,
                self._rel_x2,
                self._rel_y2,
            ) = calculate_relative_coords((x1, y1, x2, y2), model_res)

        self._rel_width = float(round(self._rel_x2 - self._rel_x1, 3))
        self._rel_height = float(round(self._rel_y2 - self._rel_y1, 3))
        self._trigger_recorder = False
        self._relevant = False
        self._filter_hit = None

    @property
    def label(self):
        """Return label of the object."""
        return self._label

    @property
    def confidence(self):
        """Return confidence of the object."""
        return self._confidence

    @property
    def rel_width(self):
        """Return relative width of the object."""
        return self._rel_width

    @property
    def rel_height(self):
        """Return relative height of the object."""
        return self._rel_height

    @property
    def rel_x1(self):
        """Return relative x1 of the object."""
        return zero_if_negative(self._rel_x1)

    @property
    def rel_y1(self):
        """Return relative y1 of the object."""
        return zero_if_negative(self._rel_y1)

    @property
    def rel_x2(self):
        """Return relative x2 of the object."""
        return zero_if_negative(self._rel_x2)

    @property
    def rel_y2(self):
        """Return relative y2 of the object."""
        return zero_if_negative(self._rel_y2)

    @property
    def formatted(self):
        """Return object data in a single dictionary."""
        payload = {}
        payload["label"] = self.label
        payload["confidence"] = self.confidence
        payload["rel_width"] = self.rel_width
        payload["rel_height"] = self.rel_height
        payload["rel_x1"] = self.rel_x1
        payload["rel_y1"] = self.rel_y1
        payload["rel_x2"] = self.rel_x2
        payload["rel_y2"] = self.rel_y2
        return payload

    @property
    def trigger_recorder(self):
        """Return if object should trigger the recorder."""
        return self._trigger_recorder

    @trigger_recorder.setter
    def trigger_recorder(self, value):
        self._trigger_recorder = value

    @property
    def relevant(self):
        """Return if object is relevant.

        Relevant means it passed through all filters.
        This does not mean the object will trigger the recorder.
        """
        return self._relevant

    @relevant.setter
    def relevant(self, value):
        self._relevant = value

    @property
    def filter_hit(self):
        """Return which filter that discarded the object."""
        return self._filter_hit

    @filter_hit.setter
    def filter_hit(self, value):
        self._filter_hit = value

    def as_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return self.formatted


def zero_if_negative(value):
    """Return zero if value is less than zero.

    Objects that are close to the edge of the frame might produce negative coordinates
    which causes problems when converting to absolute coordinates.
    This mitigates that.
    """
    if value < 0:
        return 0
    return value


@dataclass
class EventDetectedObjectsData:
    """Event with information on objects in field of view or zone."""

    camera_identifier: str
    shared_frame: SharedFrame | None
    objects: list[DetectedObject]
    zone: Any = None
