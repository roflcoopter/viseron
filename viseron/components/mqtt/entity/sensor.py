"""MQTT sensor entity."""
from viseron.helpers.entity.sensor import SensorEntity

from . import MQTTEntity


class SensorMQTTEntity(MQTTEntity[SensorEntity]):
    """Base sensor MQTT entity class."""
