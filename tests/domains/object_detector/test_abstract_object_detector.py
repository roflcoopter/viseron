"""Tests for AbstractObjectDetector functionality."""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass
from queue import Empty
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import numpy.typing as npt
import pytest
import voluptuous as vol

from viseron.domain_registry import DomainState
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.domains.motion_detector.const import DOMAIN as MOTION_DETECTOR_DOMAIN
from viseron.domains.object_detector import AbstractObjectDetector, ensure_min_max
from viseron.domains.object_detector.const import (
    CONFIG_CAMERAS,
    CONFIG_COORDINATES,
    CONFIG_FPS,
    CONFIG_LABEL_CONFIDENCE,
    CONFIG_LABEL_HEIGHT_MAX,
    CONFIG_LABEL_HEIGHT_MIN,
    CONFIG_LABEL_LABEL,
    CONFIG_LABEL_REQUIRE_MOTION,
    CONFIG_LABEL_STORE,
    CONFIG_LABEL_STORE_INTERVAL,
    CONFIG_LABEL_TRIGGER_EVENT_RECORDING,
    CONFIG_LABEL_WIDTH_MAX,
    CONFIG_LABEL_WIDTH_MIN,
    CONFIG_LABELS,
    CONFIG_LOG_ALL_OBJECTS,
    CONFIG_MASK,
    CONFIG_MAX_FRAME_AGE,
    CONFIG_SCAN_ON_MOTION_ONLY,
    CONFIG_ZONE_NAME,
    CONFIG_ZONES,
    DEFAULT_FPS,
    DEFAULT_LABEL_CONFIDENCE,
    DEFAULT_LABEL_HEIGHT_MAX,
    DEFAULT_LABEL_HEIGHT_MIN,
    DEFAULT_LABEL_REQUIRE_MOTION,
    DEFAULT_LABEL_STORE,
    DEFAULT_LABEL_STORE_INTERVAL,
    DEFAULT_LABEL_TRIGGER_EVENT_RECORDING,
    DEFAULT_LABEL_WIDTH_MAX,
    DEFAULT_LABEL_WIDTH_MIN,
    DEFAULT_LOG_ALL_OBJECTS,
    DEFAULT_MAX_FRAME_AGE,
    DEFAULT_SCAN_ON_MOTION_ONLY,
)
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.domains.object_detector.zone import Zone
from viseron.helpers.filter import Filter

from tests.common import MockCamera, MockComponent
from tests.conftest import MockViseron

# pylint: disable=protected-access  # Accessing protected members for testing

# ============================================================================
# Constants
# ============================================================================

CAMERA_IDENTIFIER = "test_camera"
COMPONENT = "test_object_detector"
CAMERA_RESOLUTION = (640, 480)

# ============================================================================
# Test Implementation of AbstractObjectDetector
# ============================================================================


class ConcreteObjectDetector(AbstractObjectDetector):
    """Concrete implementation for testing AbstractObjectDetector.

    Provides minimal implementations of the two abstract methods required by
    AbstractObjectDetector, delegating all real logic to the base class.
    Tests control detection results via set_return_objects().

    The MockObjectDetector defined in tests/common.py cannot be used here
    because it replaces the base-class methods rather than implementing the
    abstract ones, so filtering, zone, and event logic would not run.
    """

    def __init__(
        self,
        vis: MockViseron,
        config: dict[str, Any],
        camera_identifier: str,
    ) -> None:
        super().__init__(vis, COMPONENT, config, camera_identifier)
        self._return_objects_result: list[DetectedObject] | None = []

    def preprocess(self, frame: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        """Return the frame unchanged (no-op preprocessing for tests)."""
        return frame

    def return_objects(
        self, frame: npt.NDArray[np.uint8]
    ) -> list[DetectedObject] | None:
        """Getter for objects result."""
        return self._return_objects_result

    def set_return_objects(self, objects: list[DetectedObject] | None) -> None:
        """Configure what return_objects() will return on subsequent calls."""
        self._return_objects_result = objects


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def setup_camera(vis: MockViseron) -> MockCamera:
    """Register a camera and the test component in the Viseron registry.

    MockCamera registers itself under CAMERA_DOMAIN when passed a vis instance.
    MockComponent registers the component so the detector's domain registration
    succeeds.

    Args:
        vis: MockViseron instance (dispatch_event already mocked).

    Returns:
        Registered MockCamera with CAMERA_RESOLUTION set.
    """
    MockComponent(vis, COMPONENT)
    return MockCamera(vis, identifier=CAMERA_IDENTIFIER, resolution=CAMERA_RESOLUTION)


@pytest.fixture(autouse=True)
def patch_restartable_thread():
    """Patch RestartableThread so the real constructor never spawns a live thread.

    This is the *only* constructor side effect that requires patching:
    RestartableThread.start() would launch a background OS thread. All other
    heavyweight operations (add_entity, listen_event, register_signal_handler,
    dispatch_event) are already no-ops on MockViseron.

    The patch targets the import site inside the object_detector domain module
    so that ConcreteObjectDetector.__init__ → AbstractObjectDetector.__init__
    receives a MagicMock thread object throughout the test suite.

    Yields:
        The MagicMock that replaced RestartableThread. Tests that need to assert
        on thread construction or startup can request this fixture by name.
    """
    with patch(
        "viseron.domains.object_detector.RestartableThread", autospec=True
    ) as mock_thread_cls:
        # Make the constructor return a controllable mock instance so that
        # tests which inspect _object_detection_thread can use it naturally.
        mock_thread_cls.return_value = MagicMock()
        yield mock_thread_cls


@pytest.fixture
def base_config() -> dict[str, Any]:
    """Return a minimal valid configuration dict with all keys set to their defaults.

    Tests that need non-default settings should mutate a copy of this dict (or
    call add_label_config / add_zone_config on it) before constructing the
    detector.

    Returns:
        Configuration dictionary matching the shape expected by AbstractObjectDetector.
    """
    return {
        CONFIG_CAMERAS: {
            CAMERA_IDENTIFIER: {
                CONFIG_FPS: DEFAULT_FPS,
                CONFIG_SCAN_ON_MOTION_ONLY: DEFAULT_SCAN_ON_MOTION_ONLY,
                CONFIG_LABELS: [],
                CONFIG_MAX_FRAME_AGE: DEFAULT_MAX_FRAME_AGE,
                CONFIG_LOG_ALL_OBJECTS: DEFAULT_LOG_ALL_OBJECTS,
                CONFIG_MASK: [],
                CONFIG_ZONES: [],
            }
        }
    }


@pytest.fixture
def mock_shared_frame() -> SharedFrame:
    """Return a mock SharedFrame with a current capture_time.

    capture_time is set to the current wall-clock time so that the real
    _object_detection frame-age check (frame_time - capture_time > max_frame_age)
    does not discard the frame. Tests that need a stale frame should override
    capture_time explicitly.

    Returns:
        MagicMock spec'd to SharedFrame with camera_identifier and capture_time set.
    """
    mock_frame = MagicMock(spec=SharedFrame)
    mock_frame.camera_identifier = CAMERA_IDENTIFIER
    mock_frame.capture_time = time.time()
    return mock_frame


# ============================================================================
# Helper Functions
# ============================================================================


def create_detected_object(
    label: str,
    confidence: float,
    rel_x1: float = 0.1,
    rel_y1: float = 0.1,
    rel_x2: float = 0.5,
    rel_y2: float = 0.5,
) -> DetectedObject:
    """Create a DetectedObject from relative coordinates.

    Args:
        label: Object class label (e.g. "person", "car").
        confidence: Detection confidence score in [0.0, 1.0].
        rel_x1: Relative left edge (default 0.1).
        rel_y1: Relative top edge (default 0.1).
        rel_x2: Relative right edge (default 0.5).
        rel_y2: Relative bottom edge (default 0.5).

    Returns:
        DetectedObject constructed against CAMERA_RESOLUTION.
    """
    return DetectedObject.from_relative(
        label=label,
        confidence=confidence,
        rel_x1=rel_x1,
        rel_y1=rel_y1,
        rel_x2=rel_x2,
        rel_y2=rel_y2,
        frame_res=CAMERA_RESOLUTION,
    )


def add_label_config(
    config: dict[str, Any],
    label: str,
    confidence: float = DEFAULT_LABEL_CONFIDENCE,
    width_min: float = DEFAULT_LABEL_WIDTH_MIN,
    width_max: float = DEFAULT_LABEL_WIDTH_MAX,
    height_min: float = DEFAULT_LABEL_HEIGHT_MIN,
    height_max: float = DEFAULT_LABEL_HEIGHT_MAX,
    trigger_event_recording: bool = DEFAULT_LABEL_TRIGGER_EVENT_RECORDING,
    store: bool = DEFAULT_LABEL_STORE,
    store_interval: int = DEFAULT_LABEL_STORE_INTERVAL,
    require_motion: bool = DEFAULT_LABEL_REQUIRE_MOTION,
) -> None:
    """Append a label config entry to the config dict in-place.

    All parameters have the same defaults as the production LABEL_SCHEMA so
    tests only need to specify the values they care about.

    Args:
        config: Configuration dictionary to modify.
        label: Label name (e.g. "person").
        confidence: Minimum confidence threshold.
        width_min: Minimum relative width.
        width_max: Maximum relative width.
        height_min: Minimum relative height.
        height_max: Maximum relative height.
        trigger_event_recording: Whether to trigger event recording.
        store: Whether to store detections in the database.
        store_interval: Seconds between database stores (0 = every detection).
        require_motion: Whether motion is required for this label.
    """
    config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_LABELS].append(
        {
            CONFIG_LABEL_LABEL: label,
            CONFIG_LABEL_CONFIDENCE: confidence,
            CONFIG_LABEL_WIDTH_MIN: width_min,
            CONFIG_LABEL_WIDTH_MAX: width_max,
            CONFIG_LABEL_HEIGHT_MIN: height_min,
            CONFIG_LABEL_HEIGHT_MAX: height_max,
            CONFIG_LABEL_TRIGGER_EVENT_RECORDING: trigger_event_recording,
            CONFIG_LABEL_STORE: store,
            CONFIG_LABEL_STORE_INTERVAL: store_interval,
            CONFIG_LABEL_REQUIRE_MOTION: require_motion,
        }
    )


def _register_motion_detector(vis: MockViseron) -> None:
    """Register a stub motion detector domain so scan_on_motion_only is honoured.

    Without this, the real constructor falls into the DomainNotRegisteredError
    branch and silently forces scan_on_motion_only=False.
    """
    vis._domain_registry.register(
        component_name="motion",
        component_path="viseron.domains.motion_detector",
        domain=MOTION_DETECTOR_DOMAIN,
        identifier=CAMERA_IDENTIFIER,
        config={},
        require_domains=None,
        optional_domains=None,
    )
    entry = vis._domain_registry._get_entry(MOTION_DETECTOR_DOMAIN, CAMERA_IDENTIFIER)
    if entry:
        entry.instance = MagicMock()
        entry.state = DomainState.LOADED


# ============================================================================
# ensure_min_max Tests
# ============================================================================


def test_ensure_min_max_valid() -> None:
    """ensure_min_max returns the dict unchanged when min < max for both axes."""
    original = {"height_min": 0, "height_max": 1, "width_min": 0, "width_max": 1}
    assert ensure_min_max(original) is original


def test_ensure_min_max_height_equal_raises() -> None:
    """ensure_min_max raises vol.Invalid when height_min == height_max."""
    with pytest.raises(vol.Invalid):
        ensure_min_max(
            {"height_min": 1, "height_max": 1, "width_min": 0, "width_max": 1}
        )


def test_ensure_min_max_width_equal_raises() -> None:
    """ensure_min_max raises vol.Invalid when width_min == width_max."""
    with pytest.raises(vol.Invalid):
        ensure_min_max(
            {"height_min": 0, "height_max": 1, "width_min": 1, "width_max": 1}
        )


def test_ensure_min_max_height_inverted_raises() -> None:
    """ensure_min_max raises vol.Invalid when height_min > height_max."""
    with pytest.raises(vol.Invalid):
        ensure_min_max(
            {"height_min": 0.8, "height_max": 0.2, "width_min": 0, "width_max": 1}
        )


def test_ensure_min_max_width_inverted_raises() -> None:
    """ensure_min_max raises vol.Invalid when width_min > width_max."""
    with pytest.raises(vol.Invalid):
        ensure_min_max(
            {"height_min": 0, "height_max": 1, "width_min": 0.9, "width_max": 0.1}
        )


# ============================================================================
# Constructor / Initialisation Tests
# ============================================================================


def test_constructor_default_properties(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """Constructor sets expected default property values."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert det.fps == DEFAULT_FPS
    assert det.mask == []
    assert det.min_confidence == 1.0
    assert det.objects_in_fov == []
    assert det.zones == []
    assert det.object_filters == {}


def test_constructor_creates_filters_from_labels(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """Constructor creates a Filter for each configured label."""
    add_label_config(base_config, "person")
    add_label_config(base_config, "car", confidence=0.5)

    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert set(det.object_filters.keys()) == {"person", "car"}
    assert isinstance(det.object_filters["person"], Filter)
    assert isinstance(det.object_filters["car"], Filter)


def test_constructor_creates_zones(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """Constructor creates a Zone for each zone config entry."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_ZONES] = [
        {
            CONFIG_ZONE_NAME: "front_yard",
            CONFIG_COORDINATES: [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100},
                {"x": 0, "y": 100},
            ],
            CONFIG_LABELS: [],
        }
    ]

    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert len(det.zones) == 1
    assert isinstance(det.zones[0], Zone)
    assert det.zones[0].name == "front_yard"


def test_constructor_computes_min_confidence_from_labels(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """min_confidence is the lowest confidence across all configured labels."""
    add_label_config(base_config, "person", confidence=0.8)
    add_label_config(base_config, "car", confidence=0.5)
    add_label_config(base_config, "dog", confidence=0.7)

    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert det.min_confidence == 0.5


def test_constructor_warns_when_no_labels_or_zones(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Constructor logs a warning when neither labels nor zones are configured."""
    caplog.set_level("WARNING")

    ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert "No labels or zones configured" in caplog.text


def test_constructor_populates_listeners_list(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """Constructor populates _listeners with exactly three unsubscribe callables.

    AbstractObjectDetector.__init__ appends three entries to _listeners:
      1. listen_event(EVENT_OBJECT_DETECTOR_SCAN, ...)
      2. listen_event(EVENT_SCAN_FRAMES, ...)
      3. register_signal_handler(VISERON_SIGNAL_SHUTDOWN, stop)

    We assert the length of det._listeners rather than raw mock call counts,
    because other parts of the initialisation chain (binary sensors, zone
    construction) may also call vis.listen_event internally, making absolute
    call-count assertions fragile across Viseron versions.
    """
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert len(det._listeners) == 3


def test_constructor_adds_entities(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """Constructor calls add_entity for FoV binary sensor and FPS sensor."""
    add_label_config(base_config, "person")

    ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # Aleasys called: ObjectDetectedBinarySensorFoV + ObjectDetectorFPSSensor
    # Called once per label: ObjectDetectedBinarySensorFoVLabel
    assert vis.add_entity.call_count == 3


def test_constructor_builds_mask_image(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """When a mask is configured the constructor generates _mask and _mask_image."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_MASK] = [
        {
            CONFIG_COORDINATES: [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100},
                {"x": 0, "y": 100},
            ]
        }
    ]

    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert det._mask != []
    assert det._mask_image is not None


def test_constructor_scan_on_motion_only_disabled_without_motion_detector(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """scan_on_motion_only is forced False when no motion detector is registered."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_SCAN_ON_MOTION_ONLY] = True

    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert det.scan_on_motion_only is False


def test_constructor_scan_on_motion_only_honoured_with_motion_detector(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """scan_on_motion_only stays True when a motion detector is registered."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_SCAN_ON_MOTION_ONLY] = True
    _register_motion_detector(vis)

    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert det.scan_on_motion_only is True


def test_constructor_scan_on_motion_only_stays_false_when_configured_false(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """When scan_on_motion_only is False the motion detector is not consulted."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_SCAN_ON_MOTION_ONLY] = False

    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert det.scan_on_motion_only is False


def test_constructor_starts_detection_thread(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    patch_restartable_thread: MagicMock,
) -> None:
    """Constructor instantiates and starts the RestartableThread exactly once.

    patch_restartable_thread (via autouse) already patches RestartableThread for all
    tests; here we request it explicitly so we can assert on the mock class and
    the mock instance it returned.
    """
    mock_cls = patch_restartable_thread
    mock_instance = mock_cls.return_value

    ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    mock_cls.assert_called_once()
    mock_instance.start.assert_called_once()


# ============================================================================
# Filter FoV Tests - Confidence Filtering
# ============================================================================


def test_filter_fov_confidence_pass(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Objects whose confidence exceeds the threshold pass the filter."""
    add_label_config(base_config, "person", confidence=0.5)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.8)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is True
    assert detector.objects_in_fov == [obj]


def test_filter_fov_confidence_fail(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Objects whose confidence is below the threshold are filtered out."""
    add_label_config(base_config, "person", confidence=0.8)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.5)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is False
    assert obj.filter_hit == "confidence"
    assert detector.objects_in_fov == []


def test_filter_fov_confidence_boundary(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Confidence exactly equal to the threshold fails (filter uses strict >)."""
    add_label_config(base_config, "person", confidence=0.5)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.5)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is False
    assert detector.objects_in_fov == []


# ============================================================================
# Filter FoV Tests - Width Filtering
# ============================================================================


def test_filter_fov_width_pass(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Objects within the configured width range pass the filter."""
    add_label_config(base_config, "person", width_min=0.1, width_max=0.9)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # rel_width = 0.5 - 0.1 = 0.4, comfortably inside [0.1, 0.9]
    obj = create_detected_object("person", confidence=0.9, rel_x1=0.1, rel_x2=0.5)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is True
    assert detector.objects_in_fov == [obj]


def test_filter_fov_width_too_small(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Objects narrower than width_min are filtered out."""
    add_label_config(base_config, "person", width_min=0.3, width_max=0.9)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # rel_width = 0.2 - 0.1 = 0.1, below min of 0.3
    obj = create_detected_object("person", confidence=0.9, rel_x1=0.1, rel_x2=0.2)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is False
    assert obj.filter_hit == "width"
    assert detector.objects_in_fov == []


def test_filter_fov_width_too_large(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Objects wider than width_max are filtered out."""
    add_label_config(base_config, "person", width_min=0.1, width_max=0.5)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # rel_width = 0.9 - 0.1 = 0.8, above max of 0.5
    obj = create_detected_object("person", confidence=0.9, rel_x1=0.1, rel_x2=0.9)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is False
    assert obj.filter_hit == "width"
    assert detector.objects_in_fov == []


# ============================================================================
# Filter FoV Tests - Height Filtering
# ============================================================================


def test_filter_fov_height_pass(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Objects within the configured height range pass the filter."""
    add_label_config(base_config, "person", height_min=0.1, height_max=0.9)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # rel_height = 0.5 - 0.1 = 0.4, inside [0.1, 0.9]
    obj = create_detected_object("person", confidence=0.9, rel_y1=0.1, rel_y2=0.5)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is True
    assert detector.objects_in_fov == [obj]


def test_filter_fov_height_too_small(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Objects shorter than height_min are filtered out."""
    add_label_config(base_config, "person", height_min=0.3, height_max=0.9)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # rel_height = 0.2 - 0.1 = 0.1, below min of 0.3
    obj = create_detected_object("person", confidence=0.9, rel_y1=0.1, rel_y2=0.2)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is False
    assert obj.filter_hit == "height"
    assert detector.objects_in_fov == []


def test_filter_fov_height_too_large(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Objects taller than height_max are filtered out."""
    add_label_config(base_config, "person", height_min=0.1, height_max=0.5)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # rel_height = 0.9 - 0.1 = 0.8, above max of 0.5
    obj = create_detected_object("person", confidence=0.9, rel_y1=0.1, rel_y2=0.9)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is False
    assert obj.filter_hit == "height"
    assert detector.objects_in_fov == []


# ============================================================================
# Filter FoV Tests - Combined Filters
# ============================================================================


def test_filter_fov_all_filters_pass(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Objects satisfying all three filter dimensions are marked relevant."""
    add_label_config(
        base_config,
        "person",
        confidence=0.5,
        width_min=0.2,
        width_max=0.8,
        height_min=0.2,
        height_max=0.8,
    )
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # width=0.4, height=0.4, confidence=0.9 — all pass
    obj = create_detected_object(
        "person",
        confidence=0.9,
        rel_x1=0.2,
        rel_x2=0.6,
        rel_y1=0.2,
        rel_y2=0.6,
    )
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is True
    assert obj.filter_hit is None
    assert detector.objects_in_fov == [obj]


def test_filter_fov_confidence_blocks_before_width_and_height(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """filter_object short-circuits: confidence failure prevents width/height check."""
    add_label_config(
        base_config,
        "person",
        confidence=0.9,
        width_min=0.2,
        width_max=0.8,
        height_min=0.2,
        height_max=0.8,
    )
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.5)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is False
    assert obj.filter_hit == "confidence"
    assert detector.objects_in_fov == []


def test_filter_fov_width_blocks_before_height(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """filter_object short-circuits: width failure prevents height check."""
    add_label_config(
        base_config,
        "person",
        confidence=0.5,
        width_min=0.5,
        width_max=0.9,
    )
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # width = 0.1 (below min); confidence passes
    obj = create_detected_object("person", confidence=0.9, rel_x1=0.1, rel_x2=0.2)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.relevant is False
    assert obj.filter_hit == "width"
    assert detector.objects_in_fov == []


# ============================================================================
# Filter FoV Tests - Multiple Objects
# ============================================================================


def test_filter_fov_multiple_objects_mixed_results(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Each object in the list is evaluated independently."""
    add_label_config(base_config, "person", confidence=0.7)
    add_label_config(base_config, "car", confidence=0.5)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj_person_pass = create_detected_object("person", confidence=0.9)
    obj_person_fail = create_detected_object("person", confidence=0.5)
    obj_car_pass = create_detected_object("car", confidence=0.8)

    detector.filter_fov(
        mock_shared_frame, [obj_person_pass, obj_person_fail, obj_car_pass]
    )

    assert obj_person_pass.relevant is True
    assert obj_person_fail.relevant is False
    assert obj_car_pass.relevant is True
    assert len(detector.objects_in_fov) == 2
    assert obj_person_pass in detector.objects_in_fov
    assert obj_car_pass in detector.objects_in_fov


def test_filter_fov_unknown_label_is_ignored(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Objects whose label has no configured filter entry are skipped."""
    add_label_config(base_config, "person")
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj_cat = create_detected_object("cat", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj_cat])

    assert obj_cat.relevant is False
    assert detector.objects_in_fov == []


def test_filter_fov_empty_objects_list(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """filter_fov handles an empty object list without raising."""
    add_label_config(base_config, "person", confidence=0.5)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    detector.filter_fov(mock_shared_frame, [])

    assert detector.objects_in_fov == []


# ============================================================================
# Filter FoV Tests - Event Recording Trigger
# ============================================================================


def test_filter_fov_trigger_event_recording_set_when_enabled(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Passing objects have trigger_event_recording set when configured True."""
    add_label_config(base_config, "person", trigger_event_recording=True)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.trigger_event_recording is True


def test_filter_fov_trigger_event_recording_not_set_when_disabled(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Passing objects do not have trigger_event_recording set when configured False."""
    add_label_config(base_config, "person", trigger_event_recording=False)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.trigger_event_recording is False


# ============================================================================
# Filter FoV Tests - Storage
# ============================================================================


def test_filter_fov_store_flag_set_on_first_detection(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """store=True with store_interval=0 stores on every detection."""
    add_label_config(base_config, "person", store=True, store_interval=0)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.store is True


def test_filter_fov_store_flag_not_set_when_disabled(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """store=False means the object is never marked for storage."""
    add_label_config(base_config, "person", store=False)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj])

    assert obj.store is False


def test_filter_fov_store_interval_prevents_consecutive_stores(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """The store_interval prevents back-to-back database writes for the same label.

    The Filter initialises _last_stored = utcnow() - store_interval, so the
    very first detection always stores. Immediately calling filter_fov a second
    time is within the interval and must NOT store again.
    """
    add_label_config(base_config, "person", store=True, store_interval=1000)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj1 = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj1])
    assert obj1.store is True  # first detection: interval has passed since init

    obj2 = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj2])
    assert obj2.store is False  # second detection: still within the 1000-second window


# ============================================================================
# Filter FoV Tests - Events
# ============================================================================


def test_filter_fov_dispatches_event_when_objects_change(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """filter_fov dispatches an event when the FOV object list changes."""
    add_label_config(base_config, "person")
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)
    vis.dispatch_event.reset_mock()

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj])

    assert vis.dispatch_event.called


def test_filter_fov_no_event_when_objects_unchanged(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """filter_fov suppresses the dispatch when the FOV list has not changed."""
    add_label_config(base_config, "person")
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.9)

    detector.filter_fov(mock_shared_frame, [obj])
    call_count_after_first = vis.dispatch_event.call_count

    # Identical result list — no new dispatch expected
    detector.filter_fov(mock_shared_frame, [obj])

    # The assertion relies on same-instance equality rather than value equality
    assert vis.dispatch_event.call_count == call_count_after_first


def test_filter_fov_log_all_objects_branch(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """When log_all_objects=True, logger.debug is called with 'All objects:'."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_LOG_ALL_OBJECTS] = True
    add_label_config(base_config, "person")
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)
    # Replace the real logger with a mock after construction so we don't capture
    # constructor debug lines.
    detector._logger = MagicMock()

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj])

    detector._logger.debug.assert_called_with("All objects: %s", [obj.formatted])


def test_filter_fov_log_filtered_objects_branch(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """When log_all_objects=False, logger.debug is called with 'Objects:'."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_LOG_ALL_OBJECTS] = False
    add_label_config(base_config, "person")
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)
    detector._logger = MagicMock()

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj])

    detector._logger.debug.assert_any_call("Objects: %s", [obj.formatted])


# ============================================================================
# _objects_in_fov_setter Tests
# ============================================================================


def test_objects_in_fov_setter_dispatches_on_change(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """_objects_in_fov_setter fires exactly one event when the list changes."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)
    vis.dispatch_event.reset_mock()

    obj = create_detected_object("person", confidence=0.9)
    det._objects_in_fov_setter(None, [obj])

    vis.dispatch_event.assert_called_once()


def test_objects_in_fov_setter_suppresses_event_when_unchanged(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """_objects_in_fov_setter does not fire an event when the list is identical."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)
    det._objects_in_fov = []
    vis.dispatch_event.reset_mock()

    det._objects_in_fov_setter(None, [])

    vis.dispatch_event.assert_not_called()


# ============================================================================
# Filter Zones Tests
# ============================================================================


def test_filter_zones_no_zones_does_not_raise(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """filter_zones is a no-op and does not raise when no zones are configured."""
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_zones(mock_shared_frame, [obj])  # must not raise


def test_filter_zones_calls_filter_zone_on_each_zone(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """filter_zones delegates to Zone.filter_zone for each configured zone."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_ZONES] = [
        {
            CONFIG_ZONE_NAME: "zone1",
            CONFIG_COORDINATES: [
                {"x": 0, "y": 0},
                {"x": 50, "y": 0},
                {"x": 50, "y": 50},
                {"x": 0, "y": 50},
            ],
            CONFIG_LABELS: [],
        },
        {
            CONFIG_ZONE_NAME: "zone2",
            CONFIG_COORDINATES: [
                {"x": 50, "y": 50},
                {"x": 100, "y": 50},
                {"x": 100, "y": 100},
                {"x": 50, "y": 100},
            ],
            CONFIG_LABELS: [],
        },
    ]
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.9)

    with (
        patch.object(detector.zones[0], "filter_zone") as mock_fz1,
        patch.object(detector.zones[1], "filter_zone") as mock_fz2,
    ):
        detector.filter_zones(mock_shared_frame, [obj])
        mock_fz1.assert_called_once_with(mock_shared_frame, [obj])
        mock_fz2.assert_called_once_with(mock_shared_frame, [obj])


def test_filter_zones_object_inside_zone_is_marked_relevant(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """An object inside a zone polygon that passes the zone filter is marked relevant.

    This is an end-to-end zone integration test: no mocking of filter_zone or
    Zone internals. The zone covers the entire frame [0,0]→[640,480] in absolute
    coords so any object is inside it.
    """
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_ZONES] = [
        {
            CONFIG_ZONE_NAME: "full_frame",
            CONFIG_COORDINATES: [
                {"x": 0, "y": 0},
                {"x": 640, "y": 0},
                {"x": 640, "y": 480},
                {"x": 0, "y": 480},
            ],
            CONFIG_LABELS: [
                {
                    CONFIG_LABEL_LABEL: "person",
                    CONFIG_LABEL_CONFIDENCE: 0.5,
                    CONFIG_LABEL_WIDTH_MIN: 0.0,
                    CONFIG_LABEL_WIDTH_MAX: 1.0,
                    CONFIG_LABEL_HEIGHT_MIN: 0.0,
                    CONFIG_LABEL_HEIGHT_MAX: 1.0,
                    CONFIG_LABEL_TRIGGER_EVENT_RECORDING: False,
                    CONFIG_LABEL_STORE: False,
                    CONFIG_LABEL_STORE_INTERVAL: 60,
                    CONFIG_LABEL_REQUIRE_MOTION: False,
                }
            ],
        }
    ]
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_zones(mock_shared_frame, [obj])

    assert obj.relevant is True
    assert obj in detector.zones[0].objects_in_zone


def test_filter_zones_object_outside_zone_is_excluded(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """An object outside the zone polygon is not added to objects_in_zone.

    Zone covers only the top-left quadrant [0,0]→[320,240] in absolute coords.
    Object default coords (0.1→0.5 rel) map into the quadrant, but we create
    an object in the bottom-right corner instead.
    """
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_ZONES] = [
        {
            CONFIG_ZONE_NAME: "top_left_only",
            CONFIG_COORDINATES: [
                {"x": 0, "y": 0},
                {"x": 320, "y": 0},
                {"x": 320, "y": 240},
                {"x": 0, "y": 240},
            ],
            CONFIG_LABELS: [
                {
                    CONFIG_LABEL_LABEL: "person",
                    CONFIG_LABEL_CONFIDENCE: 0.5,
                    CONFIG_LABEL_WIDTH_MIN: 0.0,
                    CONFIG_LABEL_WIDTH_MAX: 1.0,
                    CONFIG_LABEL_HEIGHT_MIN: 0.0,
                    CONFIG_LABEL_HEIGHT_MAX: 1.0,
                    CONFIG_LABEL_TRIGGER_EVENT_RECORDING: False,
                    CONFIG_LABEL_STORE: False,
                    CONFIG_LABEL_STORE_INTERVAL: 60,
                    CONFIG_LABEL_REQUIRE_MOTION: False,
                }
            ],
        }
    ]
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # Object entirely in bottom-right quadrant (rel 0.6→0.9)
    obj = create_detected_object(
        "person", confidence=0.9, rel_x1=0.6, rel_y1=0.6, rel_x2=0.9, rel_y2=0.9
    )
    detector.filter_zones(mock_shared_frame, [obj])

    assert obj not in detector.zones[0].objects_in_zone


# ============================================================================
# Properties Tests
# ============================================================================


def test_objects_in_fov_property_returns_filtered_objects(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """objects_in_fov returns only objects that passed all filters."""
    add_label_config(base_config, "person", confidence=0.5)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj1 = create_detected_object("person", confidence=0.9, rel_x1=0.1, rel_x2=0.3)
    obj2 = create_detected_object("person", confidence=0.9, rel_x1=0.6, rel_x2=0.9)
    detector.filter_fov(mock_shared_frame, [obj1, obj2])

    result = detector.objects_in_fov
    assert len(result) == 2
    assert obj1 in result
    assert obj2 in result


def test_fps_property(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """Fps property reads directly from the configuration dict."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_FPS] = 5.0
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert detector.fps == 5.0


def test_scan_on_motion_only_property(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """scan_on_motion_only property reflects the (possibly overridden) config value."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_SCAN_ON_MOTION_ONLY] = False

    assert (
        ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER).scan_on_motion_only
        is False
    )


def test_mask_property_empty_by_default(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """Mask property is an empty list when no mask is configured."""
    assert ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER).mask == []


def test_min_confidence_property(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """min_confidence is the lowest confidence across all label filters."""
    add_label_config(base_config, "person", confidence=0.8)
    add_label_config(base_config, "car", confidence=0.5)

    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert det.min_confidence == 0.5


def test_avg_fps_properties_empty_at_start(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """FPS properties return 0 when no measurements have been recorded yet."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert det.preproc_fps == 0
    assert det.inference_fps == 0
    assert det.theoretical_max_fps == 0


def test_avg_fps_properties_after_measurements(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """FPS properties compute the rounded average of recorded measurements."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    det._preproc_fps.extend([1, 2, 3])
    det._inference_fps.extend([2, 2])
    det._theoretical_max_fps.extend([5])

    assert det.preproc_fps == round((1 + 2 + 3) / 3, 1)
    assert det.inference_fps == round((2 + 2) / 2, 1)
    assert det.theoretical_max_fps == 5


# ============================================================================
# concat_labels Tests
# ============================================================================


def test_concat_labels_empty_when_no_labels_or_zones(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """concat_labels returns an empty list when no FoV labels/zones are configured."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    assert det.concat_labels() == []


def test_concat_labels_fov_labels_only(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """concat_labels returns only FoV filters when no zones are configured."""
    add_label_config(base_config, "person")
    add_label_config(base_config, "car")
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    result = det.concat_labels()

    assert len(result) == 2
    assert all(isinstance(f, Filter) for f in result)
    labels = {f._label for f in result}
    assert labels == {"person", "car"}


def test_concat_labels_zone_labels_only(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """concat_labels returns only zone filters when no FoV labels are configured."""
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_ZONES] = [
        {
            CONFIG_ZONE_NAME: "zone_a",
            CONFIG_COORDINATES: [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100},
                {"x": 0, "y": 100},
            ],
            CONFIG_LABELS: [
                {
                    CONFIG_LABEL_LABEL: "dog",
                    CONFIG_LABEL_CONFIDENCE: 0.5,
                    CONFIG_LABEL_WIDTH_MIN: 0.0,
                    CONFIG_LABEL_WIDTH_MAX: 1.0,
                    CONFIG_LABEL_HEIGHT_MIN: 0.0,
                    CONFIG_LABEL_HEIGHT_MAX: 1.0,
                    CONFIG_LABEL_TRIGGER_EVENT_RECORDING: False,
                    CONFIG_LABEL_STORE: False,
                    CONFIG_LABEL_STORE_INTERVAL: 60,
                    CONFIG_LABEL_REQUIRE_MOTION: False,
                }
            ],
        }
    ]
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    result = det.concat_labels()

    assert len(result) == 1
    assert isinstance(result[0], Filter)
    assert result[0]._label == "dog"


def test_concat_labels_fov_and_zone_labels_combined(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """concat_labels merges FoV filters first, then zone filters, in order.

    Production code: return list(self.object_filters.values()) + zone_filters
    This test verifies:
      - The total count is correct (no duplicates, no omissions).
      - FoV filters appear before zone filters.
      - All returned objects are Filter instances.
    """
    add_label_config(base_config, "person", confidence=0.8)
    add_label_config(base_config, "car", confidence=0.5)
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_ZONES] = [
        {
            CONFIG_ZONE_NAME: "zone_a",
            CONFIG_COORDINATES: [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100},
                {"x": 0, "y": 100},
            ],
            CONFIG_LABELS: [
                {
                    CONFIG_LABEL_LABEL: "dog",
                    CONFIG_LABEL_CONFIDENCE: 0.6,
                    CONFIG_LABEL_WIDTH_MIN: 0.0,
                    CONFIG_LABEL_WIDTH_MAX: 1.0,
                    CONFIG_LABEL_HEIGHT_MIN: 0.0,
                    CONFIG_LABEL_HEIGHT_MAX: 1.0,
                    CONFIG_LABEL_TRIGGER_EVENT_RECORDING: False,
                    CONFIG_LABEL_STORE: False,
                    CONFIG_LABEL_STORE_INTERVAL: 60,
                    CONFIG_LABEL_REQUIRE_MOTION: False,
                },
                {
                    CONFIG_LABEL_LABEL: "cat",
                    CONFIG_LABEL_CONFIDENCE: 0.7,
                    CONFIG_LABEL_WIDTH_MIN: 0.0,
                    CONFIG_LABEL_WIDTH_MAX: 1.0,
                    CONFIG_LABEL_HEIGHT_MIN: 0.0,
                    CONFIG_LABEL_HEIGHT_MAX: 1.0,
                    CONFIG_LABEL_TRIGGER_EVENT_RECORDING: False,
                    CONFIG_LABEL_STORE: False,
                    CONFIG_LABEL_STORE_INTERVAL: 60,
                    CONFIG_LABEL_REQUIRE_MOTION: False,
                },
            ],
        }
    ]
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    result = det.concat_labels()

    # 2 FoV + 2 zone = 4 total
    assert len(result) == 4
    assert all(isinstance(f, Filter) for f in result)

    # FoV filters come first: their labels must occupy the first two positions
    fov_labels = {f._label for f in result[:2]}
    assert fov_labels == {"person", "car"}

    # Zone filters follow: their labels must occupy the last two positions
    zone_labels = {f._label for f in result[2:]}
    assert zone_labels == {"dog", "cat"}


def test_concat_labels_multiple_zones_appended_in_order(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """Zone filters from multiple zones are appended in zone-declaration order.

    With zones [A, B], concat_labels must produce:
      FoV filters... + zone_A filters... + zone_B filters...
    """
    add_label_config(base_config, "person")
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_ZONES] = [
        {
            CONFIG_ZONE_NAME: "zone_a",
            CONFIG_COORDINATES: [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100},
                {"x": 0, "y": 100},
            ],
            CONFIG_LABELS: [
                {
                    CONFIG_LABEL_LABEL: "dog",
                    CONFIG_LABEL_CONFIDENCE: 0.5,
                    CONFIG_LABEL_WIDTH_MIN: 0.0,
                    CONFIG_LABEL_WIDTH_MAX: 1.0,
                    CONFIG_LABEL_HEIGHT_MIN: 0.0,
                    CONFIG_LABEL_HEIGHT_MAX: 1.0,
                    CONFIG_LABEL_TRIGGER_EVENT_RECORDING: False,
                    CONFIG_LABEL_STORE: False,
                    CONFIG_LABEL_STORE_INTERVAL: 60,
                    CONFIG_LABEL_REQUIRE_MOTION: False,
                }
            ],
        },
        {
            CONFIG_ZONE_NAME: "zone_b",
            CONFIG_COORDINATES: [
                {"x": 200, "y": 200},
                {"x": 300, "y": 200},
                {"x": 300, "y": 300},
                {"x": 200, "y": 300},
            ],
            CONFIG_LABELS: [
                {
                    CONFIG_LABEL_LABEL: "cat",
                    CONFIG_LABEL_CONFIDENCE: 0.5,
                    CONFIG_LABEL_WIDTH_MIN: 0.0,
                    CONFIG_LABEL_WIDTH_MAX: 1.0,
                    CONFIG_LABEL_HEIGHT_MIN: 0.0,
                    CONFIG_LABEL_HEIGHT_MAX: 1.0,
                    CONFIG_LABEL_TRIGGER_EVENT_RECORDING: False,
                    CONFIG_LABEL_STORE: False,
                    CONFIG_LABEL_STORE_INTERVAL: 60,
                    CONFIG_LABEL_REQUIRE_MOTION: False,
                }
            ],
        },
    ]
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    result = det.concat_labels()

    # 1 FoV + 1 zone_a + 1 zone_b = 3 total
    assert len(result) == 3
    assert result[0]._label == "person"  # FoV first
    assert result[1]._label == "dog"  # zone_a second
    assert result[2]._label == "cat"  # zone_b third


def test_concat_labels_same_label_in_fov_and_zone_produces_two_entries(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """Same label names in both FoV and a zone produces two independent Filter entries.

    concat_labels does no deduplication — both filters coexist because they may
    have different confidence thresholds or dimension constraints.
    """
    add_label_config(base_config, "person", confidence=0.8)
    base_config[CONFIG_CAMERAS][CAMERA_IDENTIFIER][CONFIG_ZONES] = [
        {
            CONFIG_ZONE_NAME: "zone_a",
            CONFIG_COORDINATES: [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100},
                {"x": 0, "y": 100},
            ],
            CONFIG_LABELS: [
                {
                    CONFIG_LABEL_LABEL: "person",
                    CONFIG_LABEL_CONFIDENCE: 0.5,  # different threshold from FoV
                    CONFIG_LABEL_WIDTH_MIN: 0.0,
                    CONFIG_LABEL_WIDTH_MAX: 1.0,
                    CONFIG_LABEL_HEIGHT_MIN: 0.0,
                    CONFIG_LABEL_HEIGHT_MAX: 1.0,
                    CONFIG_LABEL_TRIGGER_EVENT_RECORDING: False,
                    CONFIG_LABEL_STORE: False,
                    CONFIG_LABEL_STORE_INTERVAL: 60,
                    CONFIG_LABEL_REQUIRE_MOTION: False,
                }
            ],
        }
    ]
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    result = det.concat_labels()

    assert len(result) == 2
    confidences = {f.confidence for f in result}
    assert confidences == {0.8, 0.5}


# ============================================================================
# handle_stop_scan Tests
# ============================================================================


@dataclass
class MockEventData:
    """Mock event data with only the 'scan' field."""

    scan: bool


@dataclass
class MockEvent:
    """Mock event with only the 'data' field."""

    data: MockEventData


def test_handle_stop_scan_clears_fov_and_zones(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """handle_stop_scan(scan=False) empties objects_in_fov and all zone lists."""
    add_label_config(base_config, "person")
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    # Place an object in FOV via the real filter path
    obj = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj])
    assert len(detector.objects_in_fov) == 1

    # Inject a mock zone so we can verify objects_in_zone_setter is called
    mock_zone = MagicMock()
    detector.zones = [mock_zone]

    detector.handle_stop_scan(MockEvent(data=MockEventData(scan=False)))

    assert detector.objects_in_fov == []
    mock_zone.objects_in_zone_setter.assert_called_once_with(None, [])


def test_handle_stop_scan_dispatches_fov_event(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """handle_stop_scan triggers a dispatch_event for the FOV change."""
    add_label_config(base_config, "person")
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj])
    vis.dispatch_event.reset_mock()  # ignore the event from filter_fov

    detector.handle_stop_scan(MockEvent(data=MockEventData(scan=False)))

    vis.dispatch_event.assert_called_once()


def test_handle_stop_scan_noop_when_scan_true(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """handle_stop_scan does nothing when event.data.scan is True."""
    add_label_config(base_config, "person")
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj = create_detected_object("person", confidence=0.9)
    detector.filter_fov(mock_shared_frame, [obj])
    vis.dispatch_event.reset_mock()

    detector.handle_stop_scan(MockEvent(data=MockEventData(scan=True)))

    assert len(detector.objects_in_fov) == 1  # unchanged
    vis.dispatch_event.assert_not_called()


# ============================================================================
# Integration Tests
# ============================================================================


def test_full_detection_flow_with_filters(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """End-to-end: filter_fov correctly classifies passing and failing objects."""
    add_label_config(
        base_config,
        "person",
        confidence=0.7,
        width_min=0.2,
        width_max=0.8,
        trigger_event_recording=True,
        store=True,
        store_interval=0,
    )
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj_pass = create_detected_object(
        "person", confidence=0.9, rel_x1=0.2, rel_x2=0.6, rel_y1=0.2, rel_y2=0.6
    )
    obj_fail = create_detected_object("person", confidence=0.5)

    detector.filter_fov(mock_shared_frame, [obj_pass, obj_fail])

    assert len(detector.objects_in_fov) == 1
    assert detector.objects_in_fov[0] is obj_pass
    assert obj_pass.relevant is True
    assert obj_pass.trigger_event_recording is True
    assert obj_pass.store is True
    assert obj_fail.relevant is False
    assert obj_fail.filter_hit == "confidence"


def test_multiple_labels_with_independent_filters(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Each label's threshold is applied independently to objects of that label."""
    add_label_config(base_config, "person", confidence=0.8)
    add_label_config(base_config, "car", confidence=0.5)
    detector = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    obj_person_pass = create_detected_object("person", confidence=0.9)
    obj_person_fail = create_detected_object("person", confidence=0.7)
    obj_car_pass = create_detected_object("car", confidence=0.6)
    obj_car_fail = create_detected_object("car", confidence=0.4)

    detector.filter_fov(
        mock_shared_frame,
        [obj_person_pass, obj_person_fail, obj_car_pass, obj_car_fail],
    )

    assert len(detector.objects_in_fov) == 2
    assert obj_person_pass in detector.objects_in_fov
    assert obj_car_pass in detector.objects_in_fov
    assert obj_person_fail not in detector.objects_in_fov
    assert obj_car_fail not in detector.objects_in_fov


# ============================================================================
# Storage Insertion Tests
# ============================================================================


def make_session():
    """Return a mock DB session with execute and commit mocks.

    Used by tests that verify storage interactions without a real database.
    """
    session = MagicMock()
    session.execute = MagicMock()
    session.commit = MagicMock()
    return session


def test_insert_object_calls_db_session(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """_insert_object opens a session, executes an INSERT statement, and commits.

    Capture the session instance so we can verify all three steps.
    """
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    storage = MagicMock()
    captured_session = make_session()

    @contextlib.contextmanager
    def sess_ctx():
        yield captured_session

    storage.get_session.side_effect = sess_ctx
    det._storage = storage

    obj = create_detected_object("person", confidence=0.9)
    det._insert_object(obj, "path/to/snapshot.jpg")

    storage.get_session.assert_called_once()
    captured_session.execute.assert_called_once()
    captured_session.commit.assert_called_once()


def test_insert_objects_skips_non_stored_objects(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """_insert_objects does not call dispatch_event for objects with store=False."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    storage = MagicMock()

    @contextlib.contextmanager
    def sess_ctx():
        yield make_session()

    storage.get_session.side_effect = sess_ctx
    det._storage = storage

    obj = create_detected_object("person", confidence=0.9)
    obj.store = False
    vis.dispatch_event.reset_mock()

    det._insert_objects(None, [obj])

    vis.dispatch_event.assert_not_called()


def test_insert_objects_snapshot_and_dispatch_when_stored(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
    mock_shared_frame: SharedFrame,
) -> None:
    """Saves a snapshot and dispatches an event for store=True objects."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)

    storage = MagicMock()

    @contextlib.contextmanager
    def sess_ctx():
        yield make_session()

    storage.get_session.side_effect = sess_ctx
    det._storage = storage

    obj = create_detected_object("person", confidence=0.9)
    obj.store = True
    det._camera.save_snapshot = MagicMock(return_value="snap.jpg")
    vis.dispatch_event.reset_mock()

    det._insert_objects(mock_shared_frame, [obj])

    det._camera.save_snapshot.assert_called_once()
    assert vis.dispatch_event.called


# ============================================================================
# Thread / Lifecycle Tests
# ============================================================================

# Timeout (seconds) applied to every _object_detection() call made in tests.
# The loop runs synchronously on the calling thread, so any bug that prevents
# _kill_received from being set would block the test runner forever.  Running
# the loop in a daemon thread and joining with this timeout converts an
# infinite hang into a clear, fast failure.
_LOOP_TIMEOUT = 5.0


def _run_detection_with_timeout(det: ConcreteObjectDetector) -> None:
    """Run det._object_detection() in a daemon thread with a hard timeout.

    Args:
        det: A fully configured ConcreteObjectDetector whose _object_detection
             method is ready to call.

    Raises:
        AssertionError: If the loop does not terminate within _LOOP_TIMEOUT.
    """
    t = threading.Thread(target=det._object_detection, daemon=True)
    t.start()
    t.join(timeout=_LOOP_TIMEOUT)
    timed_out = t.is_alive()
    if timed_out:
        # Force the loop to exit so the thread stops before we raise, preventing
        # it from lingering through pytest teardown and adding further latency.
        det._kill_received = True
        t.join(
            timeout=2.0
        )  # generously short — the loop checks the flag each iteration
    assert not timed_out, (
        f"_object_detection did not exit within {_LOOP_TIMEOUT}s — "
        "the loop is stuck. Check that _kill_received is set by the test's "
        "side-effect and that no code path discards the frame before reaching it."
    )


@dataclass
class FrameData:
    """Mock frame data with only the 'shared_frame' field."""

    shared_frame: Any


@dataclass
class FrameEvent:
    """Mock frame event with only the 'data' field."""

    data: FrameData


def test_object_detection_loop_runs_detect_and_respects_kill_flag(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """_object_detection calls preprocess and return_objects, then stops on kill flag.

    The queue delivers a single fresh frame. return_objects sets _kill_received
    so the loop exits after exactly one iteration.  The loop runs in a daemon
    thread via _run_detection_with_timeout so that a bug preventing termination
    produces a clear timeout failure rather than hanging the suite.
    """
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)
    det._camera.shared_frames.get_decoded_frame_rgb = MagicMock(
        return_value=np.zeros((10, 10, 3), np.uint8)
    )
    det.preprocess = MagicMock(side_effect=lambda f: f)

    def _return_and_kill(_frame):
        det._kill_received = True
        return [create_detected_object("person", 0.5)]

    det.return_objects = MagicMock(side_effect=_return_and_kill)

    det.filter_fov = MagicMock()
    det.filter_zones = MagicMock()
    det._insert_objects = MagicMock()

    shared_frame = MagicMock()
    shared_frame.camera_identifier = CAMERA_IDENTIFIER
    shared_frame.capture_time = time.time()

    det.object_detection_queue = MagicMock()
    det.object_detection_queue.get = MagicMock(
        return_value=FrameEvent(data=FrameData(shared_frame=shared_frame))
    )

    _run_detection_with_timeout(det)

    assert det._kill_received
    det.preprocess.assert_called_once()
    det.return_objects.assert_called_once()


def test_object_detection_loop_discards_stale_frames(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """_object_detection skips frames older than max_frame_age and logs a debug msg."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)
    det._logger = MagicMock()
    det.preprocess = MagicMock()
    det.return_objects = MagicMock()

    stale_frame = MagicMock()
    stale_frame.camera_identifier = CAMERA_IDENTIFIER
    stale_frame.capture_time = 0  # epoch — always stale

    call_count = 0

    # queue.get may be called as get(timeout=1) or get(1); accept both.
    def get_side_effect(_timeout=None, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return FrameEvent(data=FrameData(shared_frame=stale_frame))
        # Second call: set kill flag so the loop terminates
        det._kill_received = True
        raise Empty

    det.object_detection_queue = MagicMock()
    det.object_detection_queue.get.side_effect = get_side_effect

    _run_detection_with_timeout(det)

    # preprocess / return_objects must NOT have been called for the stale frame
    det.preprocess.assert_not_called()
    det.return_objects.assert_not_called()
    # The production code logs: f"Frame is {frame_age} seconds old. Discarding"
    # as a single f-string argument. Check that at least one debug call contains
    # the expected substring rather than matching the exact dynamic frame_age value.
    stale_log_calls = [
        call
        for call in det._logger.debug.call_args_list
        if call.args and "seconds old. Discarding" in str(call.args[0])
    ]
    assert stale_log_calls, "Expected a stale-frame debug log but none was found"


def test_stop_sets_kill_flag_and_joins_thread(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """stop() sets _kill_received=True then stops and joins the thread."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)
    det._object_detection_thread = MagicMock()
    det._kill_received = False

    det.stop()

    assert det._kill_received is True
    det._object_detection_thread.stop.assert_called_once()
    det._object_detection_thread.join.assert_called_once()


def test_unload_calls_all_listener_unsubscribes_and_stop(
    vis: MockViseron,
    setup_camera: MockCamera,
    base_config: dict[str, Any],
) -> None:
    """unload() calls every listener unsubscribe function then calls stop()."""
    det = ConcreteObjectDetector(vis, base_config, CAMERA_IDENTIFIER)
    m1, m2 = MagicMock(), MagicMock()
    det._listeners = [m1, m2]
    det.stop = MagicMock()

    det.unload()

    m1.assert_called_once()
    m2.assert_called_once()
    det.stop.assert_called_once()
