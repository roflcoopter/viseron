"""Tests for the camera domain recording schedule config schema."""

from __future__ import annotations

import pytest
import voluptuous as vol

from viseron.domains.camera.config import RECORDING_SCHEDULE_SCHEMA
from viseron.domains.camera.const import (
    CONFIG_SCHEDULE_EVENTS,
    CONFIG_SCHEDULE_TIMEZONE,
)
from viseron.helpers.validators import UNDEFINED


def test_timezone_defaults_to_undefined():
    """Omitting timezone leaves it UNDEFINED, to be resolved at runtime."""
    result = RECORDING_SCHEDULE_SCHEMA({CONFIG_SCHEDULE_EVENTS: None})
    # voluptuous calls the UNDEFINED class as a default factory, so the stored
    # value is an instance. UNDEFINED.__eq__ makes == the idiomatic check.
    assert result[CONFIG_SCHEDULE_TIMEZONE] == UNDEFINED


def test_timezone_can_be_overridden():
    """An explicit timezone is preserved."""
    result = RECORDING_SCHEDULE_SCHEMA({CONFIG_SCHEDULE_TIMEZONE: "America/New_York"})
    assert result[CONFIG_SCHEDULE_TIMEZONE] == "America/New_York"


def test_timezone_accepts_none():
    """An explicit null falls back to runtime resolution too."""
    result = RECORDING_SCHEDULE_SCHEMA({CONFIG_SCHEDULE_TIMEZONE: None})
    assert result[CONFIG_SCHEDULE_TIMEZONE] is None


def test_invalid_timezone_override_rejected():
    """An invalid timezone override fails schema validation."""
    with pytest.raises(vol.Invalid):
        RECORDING_SCHEDULE_SCHEMA({CONFIG_SCHEDULE_TIMEZONE: "Not/AZone"})
