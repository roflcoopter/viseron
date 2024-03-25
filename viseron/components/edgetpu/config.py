"""EdgeTPU configuration specials."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from viseron.config import UNSUPPORTED
from viseron.domains.image_classification.const import (
    DOMAIN as IMAGE_CLASSIFICATION_DOMAIN,
)

from .const import (
    CONFIG_CROP_CORRECTION,
    CONFIG_LABEL_PATH,
    DEFAULT_CROP_CORRECTION,
    DEFAULT_LABEL_PATH_MAP,
    DESC_CROP_CORRECTION,
    DESC_LABEL_PATH,
)

DEVICE_REGEXES = [
    re.compile(r"^:[0-9]$"),  # match ':<N>'
    re.compile(r"^(usb|pci|cpu)$"),  # match 'usb', 'pci' and 'cpu'
    re.compile(r"^(usb|pci):[0-9]$"),  # match 'usb:<N>' and 'pci:<N>'
]


def custom_convert(value):
    """Convert custom validators for the script gen_docs."""
    if isinstance(value, DeviceValidator):
        return {
            "type": "select",
            "options": [
                {"value": "<N>", "description": "Use N-th Edge TPU"},
                {"value": "usb", "description": "Use any USB Edge TPU"},
                {"value": "usb:<N>", "description": "Use N-th USB Edge TPU"},
                {"value": "pci", "description": "Use any PCIe Edge TPU"},
                {"value": "pci:<N>", "description": "Use N-th PCIe Edge TPU"},
                {"value": "cpu", "description": "Run on the CPU"},
            ],
        }
    return UNSUPPORTED


class DeviceValidator:
    """Validate EdgeTPU device mapping."""

    def __init__(self) -> None:
        pass

    def __call__(self, device):
        """Check for valid EdgeTPU device name.

        Valid values are:
            ":<N>" : Use N-th Edge TPU
            "usb" : Use any USB Edge TPU
            "usb:<N>" : Use N-th USB Edge TPU
            "pci" : Use any PCIe Edge TPU
            "pci:<N>" : Use N-th PCIe Edge TPU
            "cpu" : Run on the CPU
        """
        if device is None:
            return device

        for regex in DEVICE_REGEXES:
            if regex.match(device):
                return device
        raise vol.Invalid(
            f"EdgeTPU device {device} is invalid. Please check your configuration"
        )


class DefaultLabelPath:
    """Return default label path for specified domain."""

    def __init__(self, domain, msg=None) -> None:
        self.msg = msg
        self.domain = domain

    def __call__(self, value):
        """Return default label path for specified domain."""
        if value:
            return value
        return DEFAULT_LABEL_PATH_MAP[self.domain]


def get_label_schema(domain):
    """Return domain specific schema."""
    schema: dict[vol.Optional, Any] = {
        vol.Optional(
            CONFIG_LABEL_PATH,
            default=DEFAULT_LABEL_PATH_MAP[domain],
            description=DESC_LABEL_PATH,
        ): str,
    }

    if domain == IMAGE_CLASSIFICATION_DOMAIN:
        image_classification_schema = {
            vol.Optional(
                CONFIG_LABEL_PATH,
                description=DESC_LABEL_PATH,
                default=DefaultLabelPath(domain),
            ): str,
            vol.Optional(
                CONFIG_CROP_CORRECTION,
                description=DESC_CROP_CORRECTION,
                default=DEFAULT_CROP_CORRECTION,
            ): int,
        }
        schema = {**schema, **image_classification_schema}

    return schema
