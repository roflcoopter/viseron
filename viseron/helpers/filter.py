"""Used to filter out unwanted objects."""
from viseron.config.config_object_detection import LabelConfig
from viseron.detector.detected_object import DetectedObject


class Filter:
    """Filter a recorded object against a configured label."""

    def __init__(self, object_filter: LabelConfig) -> None:
        self._label = object_filter.label
        self._confidence = object_filter.confidence
        self._width_min = object_filter.width_min
        self._width_max = object_filter.width_max
        self._height_min = object_filter.height_min
        self._height_max = object_filter.height_max
        self._triggers_recording = object_filter.triggers_recording
        self._require_motion = object_filter.require_motion
        self._post_processor = object_filter.post_processor

    def filter_confidence(self, obj: DetectedObject) -> bool:
        """Return if confidence filter is met."""
        if obj.confidence > self._confidence:
            return True
        return False

    def filter_width(self, obj: DetectedObject) -> bool:
        """Return if width filter is met."""
        if self._width_max > obj.rel_width > self._width_min:
            return True
        return False

    def filter_height(self, obj: DetectedObject) -> bool:
        """Return if height filter is met."""
        if self._height_max > obj.rel_height > self._height_min:
            return True
        return False

    def filter_object(self, obj: DetectedObject) -> bool:
        """Return if filters are met."""
        return (
            self.filter_confidence(obj)
            and self.filter_width(obj)
            and self.filter_height(obj)
        )

    @property
    def triggers_recording(self) -> bool:
        """Return if label triggers recorder."""
        return self._triggers_recording

    def require_motion(self) -> bool:
        """Return if label requires motion to trigger recorder."""
        return self._require_motion

    @property
    def post_processor(self) -> str:
        """Return post processor for label."""
        return self._post_processor
