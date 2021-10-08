"""Tests for NVR."""
from unittest.mock import patch

import pytest

import viseron.nvr as nvr


@pytest.mark.usefixtures("nvr_config_full")
class TestMQTTInterface:
    """Test MQTTInterface."""

    def test_publish_image(self, nvr_config_full, black_frame, zone):
        """Test publish image to MQTT."""
        with patch("viseron.mqtt.MQTT") as mock_mqtt:
            mock_mqtt.client = True
            mock_mqtt.publish.return_value = "testing"
            self.mqtt_interface = nvr.MQTTInterface(nvr_config_full)
            self.mqtt_interface.publish_image(
                black_frame, black_frame, [zone], (100, 100)
            )
            mock_mqtt.publish.assert_called_once()

    def test_status_state(self, nvr_config_full):
        """Test status state update."""
        with patch("viseron.mqtt.MQTT") as mock_mqtt:
            mock_mqtt.client = True
            self.mqtt_interface = nvr.MQTTInterface(nvr_config_full)
            self.mqtt_interface.status_state_callback("testing")
            mock_mqtt.publish.assert_called_once()
            assert self.mqtt_interface.status_state == "testing"


@pytest.fixture
def mock_camera(mocked_camera):
    """Mock FFMPEGCamera."""
    with patch("viseron.nvr.FFMPEGCamera", new=mocked_camera) as mock:
        yield mock


@pytest.fixture
def mock_motion_detection(mocked_motion_detection):
    """Mock MotionDetection."""
    with patch("viseron.nvr.MotionDetection", new=mocked_motion_detection) as mock:
        yield mock


@pytest.fixture
def mock_recorder(mocked_recorder):
    """Mock FFMPEGRecorder."""
    with patch("viseron.nvr.FFMPEGRecorder", new=mocked_recorder) as mock:
        yield mock


@pytest.fixture
def mock_restartable_thread(mocked_restartable_thread):
    """Mock RestartableThread."""
    with patch("viseron.nvr.RestartableThread", new=mocked_restartable_thread) as mock:
        yield mock


@pytest.mark.usefixtures("nvr_config_full")
class TestFFMPEGNVR:
    """Test FFMPEGNVR."""

    @pytest.mark.parametrize(
        "motion_detection_trigger_detector, object_detection_enable, event_set, event_clear",
        [
            (True, True, 1, 1),
            (True, False, 1, 0),
            (False, True, 1, 1),
            (False, False, 0, 1),
        ],
    )
    def test_init(
        self,
        motion_detection_trigger_detector,
        object_detection_enable,
        event_set,
        event_clear,
        mocked_detector,
        mock_camera,
        mock_motion_detection,
        mock_recorder,
        mock_restartable_thread,
        nvr_config_full,
    ):
        """Test __init__."""
        nvr_config_full.motion_detection._trigger_detector = (
            motion_detection_trigger_detector
        )
        nvr_config_full.object_detection._enable = object_detection_enable
        ffmpeg_nvr = nvr.FFMPEGNVR(nvr_config_full, mocked_detector)
        mock_camera.assert_called_once_with(nvr_config_full, mocked_detector)
        mock_motion_detection.assert_called_once_with(
            nvr_config_full, ffmpeg_nvr.camera
        )
        mock_recorder.assert_called_once_with(nvr_config_full)

        assert mock_restartable_thread.call_count == 2
        assert (
            ffmpeg_nvr.camera.stream.decoders.__getitem__().scan.set.call_count
            == event_set
        )
        assert (
            ffmpeg_nvr.camera.stream.decoders.__getitem__().scan.clear.call_count
            == event_clear
        )
