"""Tests for the MQTT external motion detector."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from viseron.components.mqtt.const import (
    COMPONENT as MQTT_COMPONENT,
    CONFIG_PAYLOAD_OFF,
    CONFIG_PAYLOAD_ON,
    CONFIG_TOPIC,
)
from viseron.components.mqtt.helpers import SubscribeTopic
from viseron.components.mqtt.motion_detector import MQTTMotionDetector
from viseron.domains.motion_detector.const import (
    CONFIG_CAMERAS,
    CONFIG_MAX_MOTION_DURATION,
    CONFIG_MAX_RECORDER_KEEPALIVE,
    CONFIG_RECORDER_KEEPALIVE,
    CONFIG_TRIGGER_EVENT_RECORDING,
)

from tests.common import MockCamera, MockComponent

if TYPE_CHECKING:
    from tests.conftest import MockViseron


CAMERA_IDENTIFIER = "test_camera"
TOPIC = "viseron/test_camera/motion"


class DummyMessage:
    """Minimal stand-in for a paho-mqtt MQTTMessage."""

    def __init__(self, payload: str) -> None:
        self.payload = payload.encode()
        self.topic = TOPIC


@pytest.fixture
def mqtt_client(vis: MockViseron) -> MagicMock:
    """Register a MagicMock MQTT client under the component slot."""
    client = MagicMock()
    vis.data[MQTT_COMPONENT] = client
    MockComponent(vis, "mqtt")
    return client


@pytest.fixture
def camera(vis: MockViseron) -> MockCamera:
    """Register a camera."""
    return MockCamera(vis, identifier=CAMERA_IDENTIFIER)


def _config(**overrides: Any) -> dict:
    cam_cfg = {
        CONFIG_TRIGGER_EVENT_RECORDING: True,
        CONFIG_RECORDER_KEEPALIVE: False,
        CONFIG_MAX_RECORDER_KEEPALIVE: 0,
        CONFIG_MAX_MOTION_DURATION: 0,
        CONFIG_TOPIC: TOPIC,
        CONFIG_PAYLOAD_ON: "on",
        CONFIG_PAYLOAD_OFF: "off",
    }
    cam_cfg.update(overrides)
    return {CONFIG_CAMERAS: {CAMERA_IDENTIFIER: cam_cfg}}


def _make_detector(
    vis: MockViseron, _mqtt_client: MagicMock, **overrides: Any
) -> MQTTMotionDetector:
    return MQTTMotionDetector(vis, _config(**overrides), CAMERA_IDENTIFIER)


@pytest.mark.usefixtures("camera")
def test_subscribes_to_configured_topic(
    vis: MockViseron, mqtt_client: MagicMock
) -> None:
    """The detector must subscribe to the configured MQTT topic on init."""
    _make_detector(vis, mqtt_client)
    assert mqtt_client.subscribe.call_count == 1
    sub = mqtt_client.subscribe.call_args.args[0]
    assert isinstance(sub, SubscribeTopic)
    assert sub.topic == TOPIC


@pytest.mark.usefixtures("camera")
def test_payload_on_sets_motion_true(vis: MockViseron, mqtt_client: MagicMock) -> None:
    """A 'payload_on' message must mark motion as detected."""
    detector = _make_detector(vis, mqtt_client)
    detector._on_message(DummyMessage("on"))
    assert detector.motion_detected is True


@pytest.mark.usefixtures("camera")
def test_payload_off_sets_motion_false(
    vis: MockViseron, mqtt_client: MagicMock
) -> None:
    """A 'payload_off' message must clear motion."""
    detector = _make_detector(vis, mqtt_client)
    detector._on_message(DummyMessage("on"))
    detector._on_message(DummyMessage("off"))
    assert detector.motion_detected is False


@pytest.mark.usefixtures("camera")
def test_custom_payloads(vis: MockViseron, mqtt_client: MagicMock) -> None:
    """Custom payload_on / payload_off strings must be honoured."""
    detector = _make_detector(
        vis, mqtt_client, payload_on="MOTION", payload_off="CLEAR"
    )
    detector._on_message(DummyMessage("MOTION"))
    assert detector.motion_detected is True
    detector._on_message(DummyMessage("CLEAR"))
    assert detector.motion_detected is False


@pytest.mark.usefixtures("camera")
def test_json_payload_with_detected_field(
    vis: MockViseron, mqtt_client: MagicMock
) -> None:
    """JSON payloads of {detected: bool} must drive the state."""
    detector = _make_detector(vis, mqtt_client)
    detector._on_message(DummyMessage(json.dumps({"detected": True})))
    assert detector.motion_detected is True
    detector._on_message(DummyMessage(json.dumps({"detected": False})))
    assert detector.motion_detected is False


@pytest.mark.usefixtures("camera")
def test_unrecognised_payload_is_ignored(
    vis: MockViseron, mqtt_client: MagicMock
) -> None:
    """Garbage payloads must not change motion state."""
    detector = _make_detector(vis, mqtt_client)
    detector._on_message(DummyMessage("on"))
    detector._on_message(DummyMessage("hello world"))
    assert detector.motion_detected is True
