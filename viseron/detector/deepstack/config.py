"""Deepstack config."""
from os import PathLike
from typing import Union

from voluptuous import Any, Optional, Required

from viseron.detector import AbstractDetectorConfig

from .defaults import TIMEOUT

SCHEMA = AbstractDetectorConfig.SCHEMA.extend(
    {
        Required("host"): str,
        Required("port"): int,
        Optional("image_width", default=None): Any(int, None),
        Optional("image_height", default=None): Any(int, None),
        Optional("custom_model", default=None): Any(str, None),
        Optional("api_key", default=None): Any(str, None),
        Optional("timeout", default=TIMEOUT): int,
    }
)


class Config(AbstractDetectorConfig):
    """Deepstack object detection config."""

    def __init__(self, detector_config):
        super().__init__(detector_config)
        self._host = detector_config["host"]
        self._port = detector_config["port"]
        self._image_width = detector_config["image_width"]
        self._image_height = detector_config["image_height"]
        self._custom_model = detector_config["custom_model"]
        self._api_key = detector_config["api_key"]
        self._timeout = detector_config["timeout"]

    @property
    def host(self) -> str:
        """Return Deepstack host."""
        return self._host

    @property
    def port(self) -> int:
        """Return Deepstack port."""
        return self._port

    @property
    def image_width(self) -> Union[int, None]:
        """Return width that images will be resized to before running detection."""
        return self._image_width

    @property
    def image_height(self) -> Union[int, None]:
        """Return height that images will be resized to before running detection."""
        return self._image_height

    @property
    def custom_model(self) -> PathLike:
        """Return model path."""
        return self._custom_model

    @property
    def api_key(self) -> str:
        """Return API key."""
        return self._api_key

    @property
    def timeout(self) -> int:
        """Return timeout."""
        return self._timeout
