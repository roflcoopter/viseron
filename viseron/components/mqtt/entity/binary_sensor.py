"""MQTT binary sensor entity."""
from viseron.helpers.entity.binary_sensor import BinarySensorEntity

from . import MQTTEntity


class BinarySensorMQTTEntity(MQTTEntity[BinarySensorEntity]):
    """Base binary sensor MQTT entity class."""
