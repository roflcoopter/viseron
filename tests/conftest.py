"""Viseron pytest configuration."""
from unittest.mock import MagicMock, mock_open, patch

import cv2
import numpy as np
import pytest

from viseron.camera.frame import Frame
from viseron.config import NVRConfig, ViseronConfig, load_config
from viseron.zones import Zone

YAML_CONFIG = """
cameras:
  - name: Test stream
    host: wowzaec2demo.streamlock.net
    port: 554
    path: /vod/mp4:BigBuckBunny_115k.mov
    width: 240
    height: 160
    fps: 24
logging:
  level: debug
"""
YAML_CONFIG_SECRET = """
cameras:
  - name: Test stream
    host: wowzaec2demo.streamlock.net
    port: !secret port
    path: /vod/mp4:BigBuckBunny_115k.mov
"""
YAML_CONFIG_FULL = """
cameras:
  - stream_format: rtsp
    path: /vod/mp4:BigBuckBunny_115k.mov
    port: 554
    codec: h265
    name: Test stream
    host: wowzaec2demo.streamlock.net
    substream:
      port: 554
      path: /vod/mp4:BigBuckBunny_115k.mov
      codec: h264
    static_mjpeg_streams:
      my-stream:
        width: 100
        height: 100
    zones:
      - name: zone1
        points:
          - x: 0
            y: 500
          - x: 1920
            y: 500
          - x: 1920
            y: 1080
          - x: 0
            y: 1080
        labels:
          - label: person
            confidence: 0.7
            triggers_recording: true
    object_detection:
      labels:
        - label: person
          confidence: 0.8
      mask:
        - points:
            - x: 50
              y: 50
            - x: 100
              y: 50
            - x: 100
              y: 100
            - x: 50
              y: 100
    motion_detection:
      mask:
        - points:
            - x: 0
              y: 0
            - x: 50
              y: 0
            - x: 50
              y: 50
            - x: 0
              y: 50
    logging:
      level: debug
post_processors:
  face_recognition:
    type: dlib
mqtt:
  broker: dummy
"""

WIDTH = 100
HEIGHT = 100


@pytest.fixture
def simple_config() -> str:
    """Return simple yaml config."""
    return YAML_CONFIG


@pytest.fixture
def simple_config_secret() -> str:
    """Return simple yaml config with a secret."""
    return YAML_CONFIG_SECRET


@pytest.fixture
def full_config() -> str:
    """Full yaml config with."""
    return YAML_CONFIG_FULL


@pytest.fixture
def raw_config(simple_config) -> dict:
    """Return simple validated config."""
    mock = mock_open(read_data=simple_config)
    with patch("builtins.open", mock):
        return load_config()


@pytest.fixture
def raw_config_full(full_config) -> dict:
    """Full validated config."""
    mock = mock_open(read_data=full_config)
    with patch("builtins.open", mock):
        return load_config()


@pytest.fixture
def viseron_config(raw_config) -> ViseronConfig:
    """Return simple ViseronConfig."""
    return ViseronConfig(raw_config)


@pytest.fixture
def viseron_config_full(raw_config_full) -> ViseronConfig:
    """Return full ViseronConfig."""
    return ViseronConfig(raw_config_full)


@pytest.fixture
def nvr_config(viseron_config) -> NVRConfig:
    """Return simple NVRConfig."""
    return NVRConfig(
        viseron_config.cameras[0],
        viseron_config.object_detection,
        viseron_config.motion_detection,
        viseron_config.recorder,
        viseron_config.mqtt,
        viseron_config.logging,
    )


@pytest.fixture
def nvr_config_full(viseron_config_full) -> NVRConfig:
    """Return simple NVRConfig."""
    return NVRConfig(
        viseron_config_full.cameras[0],
        viseron_config_full.object_detection,
        viseron_config_full.motion_detection,
        viseron_config_full.recorder,
        viseron_config_full.mqtt,
        viseron_config_full.logging,
    )


@pytest.fixture
def resolution():
    """Return Camera resolution."""
    return (WIDTH, HEIGHT)


@pytest.fixture
def zone(nvr_config_full, resolution) -> Zone:
    """Return a Zone object."""
    return Zone(nvr_config_full.camera.zones[0], resolution, nvr_config_full)


@pytest.fixture
def black_raw_frame():
    """Return a 100x100x3 byte array filled with 0."""
    return np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)


@pytest.fixture
def black_frame(black_raw_frame):
    """Return a black Frame object."""
    frame = Frame(
        cv2.COLOR_RGB2BGR, WIDTH, int(HEIGHT * 3), black_raw_frame, WIDTH, HEIGHT
    )
    # Manually set the decoded frame to avoid errors
    frame._decoded_frame = black_raw_frame
    return frame


@pytest.fixture
def mocked_camera(resolution):
    """Return mocked camera."""
    mock = MagicMock(resolution=resolution, spec=["stream"])
    return mock


@pytest.fixture
def mocked_detector():
    """Return mocked detector."""
    mock = MagicMock(lock="Testing", spec=[])
    return mock


@pytest.fixture
def mocked_motion_detection():
    """Return mocked motion detection."""
    mock = MagicMock(spec=[])
    return mock


@pytest.fixture
def mocked_recorder():
    """Return mocked recorder."""
    mock = MagicMock(spec=[])
    return mock


@pytest.fixture
def mocked_restartable_thread():
    """Return mocked restartable thread."""
    mock = MagicMock(spec=["start"])
    mock.start.return_value = "Testing"
    return mock
