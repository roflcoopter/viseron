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
