"""Test the Filter class."""

from datetime import timedelta

from viseron.domains.motion_detector.const import CONFIG_TRIGGER_RECORDER
from viseron.domains.object_detector.const import (
    CONFIG_LABEL_CONFIDENCE,
    CONFIG_LABEL_HEIGHT_MAX,
    CONFIG_LABEL_HEIGHT_MIN,
    CONFIG_LABEL_LABEL,
    CONFIG_LABEL_REQUIRE_MOTION,
    CONFIG_LABEL_STORE,
    CONFIG_LABEL_STORE_INTERVAL,
    CONFIG_LABEL_WIDTH_MAX,
    CONFIG_LABEL_WIDTH_MIN,
)
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.helpers import utcnow
from viseron.helpers.filter import Filter

FRAME_RES = (1920, 1080)


def test_should_store() -> None:
    """Test that should_store returns the correct value."""
    _filter = Filter(
        FRAME_RES,
        {
            CONFIG_LABEL_LABEL: "person",
            CONFIG_LABEL_CONFIDENCE: 0.8,
            CONFIG_LABEL_WIDTH_MIN: 0,
            CONFIG_LABEL_WIDTH_MAX: 1,
            CONFIG_LABEL_HEIGHT_MIN: 0,
            CONFIG_LABEL_HEIGHT_MAX: 1,
            CONFIG_TRIGGER_RECORDER: True,
            CONFIG_LABEL_REQUIRE_MOTION: False,
            CONFIG_LABEL_STORE: True,
            CONFIG_LABEL_STORE_INTERVAL: 10,
        },
        [],
    )
    obj = DetectedObject("person", 0.9, 0.1, 0.1, 0.2, 0.2, FRAME_RES)
    assert _filter.should_store(obj) is True
    assert obj.store is True

    _filter._last_stored = utcnow() - timedelta(  # pylint: disable=protected-access
        seconds=5,
    )
    assert _filter.should_store(obj) is False
    assert obj.store is False
