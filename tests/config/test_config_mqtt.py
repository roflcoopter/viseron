"""Tests for mqtt config."""
import pytest

from viseron.config import config_mqtt

from tests.helpers import assert_config_instance_config_dict

MQTT_CONFIG = {
    "broker": "broker",
    "port": 1883,
    "username": "user",
    "password": "pass",
    "client_id": "viseron",
    "home_assistant": {
        "enable": True,
        "discovery_prefix": "homeassistant",
    },
    "last_will_topic": "lwt_topic",
}


@pytest.mark.parametrize(
    "mqtt, expected",
    [
        (
            {"client_id": "viseron_test_client", "last_will_topic": None},
            {
                "client_id": "viseron_test_client",
                "last_will_topic": "viseron_test_client/lwt",
            },
        ),
        (
            {"client_id": "viseron_test_client", "last_will_topic": "lwt_topic"},
            {
                "client_id": "viseron_test_client",
                "last_will_topic": "lwt_topic",
            },
        ),
    ],
)
def test_get_lwt_topic(mqtt, expected):
    """Test that get_lwet_topic is generated if missing."""
    assert config_mqtt.get_lwt_topic(mqtt) == expected


class TestMQTTConfig:
    """Test MQTTConfig."""

    def test_init(self):
        """Test instantiation."""
        config = config_mqtt.MQTTConfig(MQTT_CONFIG)
        assert_config_instance_config_dict(config, MQTT_CONFIG)
