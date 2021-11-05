"""Used to filter out unwanted objects."""
from viseron.domains.object_detector.const import (
    CONFIG_LABEL_CONFIDENCE,
    CONFIG_LABEL_HEIGHT_MAX,
    CONFIG_LABEL_HEIGHT_MIN,
    CONFIG_LABEL_LABEL,
    CONFIG_LABEL_POST_PROCESSOR,
    CONFIG_LABEL_REQUIRE_MOTION,
    CONFIG_LABEL_TRIGGER_RECORDER,
    CONFIG_LABEL_WIDTH_MAX,
    CONFIG_LABEL_WIDTH_MIN,
)
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.helpers import generate_mask, object_in_polygon


class Filter:
    """Filter a recorded object against a configured label."""

    def __init__(self, camera_resolution, object_filter, mask) -> None:
        self._camera_resolution = camera_resolution
        self._mask = generate_mask(mask)
        self._label = object_filter[CONFIG_LABEL_LABEL]
        self._confidence = object_filter[CONFIG_LABEL_CONFIDENCE]
        self._width_min = object_filter[CONFIG_LABEL_WIDTH_MIN]
        self._width_max = object_filter[CONFIG_LABEL_WIDTH_MAX]
        self._height_min = object_filter[CONFIG_LABEL_HEIGHT_MIN]
        self._height_max = object_filter[CONFIG_LABEL_HEIGHT_MAX]
        self._trigger_recorder = object_filter[CONFIG_LABEL_TRIGGER_RECORDER]
        self._require_motion = object_filter[CONFIG_LABEL_REQUIRE_MOTION]
        self._post_processor = object_filter[CONFIG_LABEL_POST_PROCESSOR]

    def filter_confidence(self, obj: DetectedObject) -> bool:
        """Return if confidence filter is met."""
        if obj.confidence > self._confidence:
            return True
        obj.filter_hit = "confidence"
        return False

    def filter_width(self, obj: DetectedObject) -> bool:
        """Return if width filter is met."""
        if self._width_max > obj.rel_width > self._width_min:
            return True
        obj.filter_hit = "width"
        return False

    def filter_height(self, obj: DetectedObject) -> bool:
        """Return if height filter is met."""
        if self._height_max > obj.rel_height > self._height_min:
            return True
        obj.filter_hit = "height"
        return False

    def filter_mask(self, obj: DetectedObject) -> bool:
        """Return True if object is within mask."""
        for mask in self._mask:
            if object_in_polygon(self._camera_resolution, obj, mask):
                obj.filter_hit = "mask"
                return False
        return True

    def filter_object(self, obj: DetectedObject) -> bool:
        """Return if filters are met."""
        return (
            self.filter_confidence(obj)
            and self.filter_width(obj)
            and self.filter_height(obj)
            and self.filter_mask(obj)
        )

    @property
    def trigger_recorder(self) -> bool:
        """Return if label triggers recorder."""
        return self._trigger_recorder

    @property
    def require_motion(self) -> bool:
        """Return if label requires motion to trigger recorder."""
        return self._require_motion

    @property
    def post_processor(self) -> str:
        """Return post processor for label."""
        return self._post_processor
