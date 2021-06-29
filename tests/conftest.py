"""Viseron pytest configuration."""
from unittest import mock

import pytest

from viseron.config import NVRConfig, ViseronConfig, load_config

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
    logging:
      level: debug
post_processors:
  face_recognition:
    type: dlib
"""


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
    mock_open = mock.mock_open(read_data=simple_config)
    with mock.patch("builtins.open", mock_open):
        return load_config()


@pytest.fixture
def raw_config_full(full_config) -> dict:
    """Full validated config."""
    mock_open = mock.mock_open(read_data=full_config)
    with mock.patch("builtins.open", mock_open):
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
