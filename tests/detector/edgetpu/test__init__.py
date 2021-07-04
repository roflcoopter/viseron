"""Test EdgeTPU detector."""
from contextlib import nullcontext

import pytest
import voluptuous

from viseron.detector import edgetpu


@pytest.mark.parametrize(
    "test_input, expected, raises",
    [
        (":", ":", pytest.raises(voluptuous.error.Invalid)),
        (":1", ":1", nullcontext()),
        ("usb", "usb", nullcontext()),
        ("usb:1", "usb:1", nullcontext()),
        ("pci", "pci", nullcontext()),
        ("pci:0", "pci:0", nullcontext()),
        ("usb:", "usb:", pytest.raises(voluptuous.error.Invalid)),
        ("abcde", "abcde", pytest.raises(voluptuous.error.Invalid)),
        ("", "", pytest.raises(voluptuous.error.Invalid)),
    ],
)
def test_edgetpu_device_validator(test_input, expected, raises):
    """Test EdgeTPU device validator."""
    with raises:
        assert edgetpu.edgetpu_device_validator(test_input) == expected
