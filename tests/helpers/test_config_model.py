"""Tests for the config model base classes."""

from __future__ import annotations

import logging

import pytest
from pydantic import Field, ValidationError

from viseron.helpers.config_model import ComponentRoot, ConfigModel


class Thumbnail(ConfigModel):
    """Nested section with a deprecated key."""

    save_to_disk: bool = False
    filename_pattern: str | None = Field(
        default=None, deprecated="Thumbnails are named after the event."
    )


class Camera(ConfigModel):
    """Model with nested sections and deprecated keys."""

    host: str
    port: int = 554
    thumbnail: Thumbnail = Field(default_factory=Thumbnail)
    retain: int | None = Field(default=None, deprecated=True)
    segments_folder: str | None = Field(
        default=None, alias="segments-folder", deprecated=True
    )


class CameraRoot(ComponentRoot):
    """Root model of a component."""

    ffmpeg: Camera


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"host": "h", "prot": 1}, id="top_level"),
        pytest.param({"host": "h", "thumbnail": {"save": True}}, id="nested_section"),
    ],
)
def test_unknown_key_is_rejected(config: dict) -> None:
    """A key that the model does not know is an error and not ignored."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Camera.model_validate(config)


@pytest.mark.parametrize(
    ("config", "warning"),
    [
        pytest.param(
            {"host": "h", "thumbnail": {"filename_pattern": "x"}},
            "Config option 'filename_pattern' is deprecated and will be removed in "
            "a future version. Thumbnails are named after the event.",
            id="with_message",
        ),
        pytest.param(
            {"host": "h", "retain": 7},
            "Config option 'retain' is deprecated and will be removed in a future "
            "version.",
            id="without_message",
        ),
        pytest.param(
            {"host": "h", "segments-folder": "/segments"},
            "Config option 'segments-folder' is deprecated and will be removed in a "
            "future version.",
            id="named_by_alias",
        ),
    ],
)
def test_deprecated_key_warns_when_set(
    caplog: pytest.LogCaptureFixture, config: dict, warning: str
) -> None:
    """A deprecated key that is set is still accepted, and logs a warning."""
    with caplog.at_level(logging.WARNING):
        Camera.model_validate(config)
    assert caplog.messages == [warning]


def test_deprecated_key_is_silent_when_unset(caplog: pytest.LogCaptureFixture) -> None:
    """A deprecated key that is not set logs nothing."""
    with caplog.at_level(logging.WARNING):
        Camera.model_validate({"host": "h"})
    assert caplog.messages == []


def test_component_root_ignores_other_components() -> None:
    """The root model is validated against the whole config, and keeps its own key."""
    root = CameraRoot.model_validate({"ffmpeg": {"host": "h"}, "mqtt": {"broker": "b"}})
    assert root.ffmpeg.host == "h"
    assert root.model_dump() == {
        "ffmpeg": {
            "host": "h",
            "port": 554,
            "thumbnail": {"save_to_disk": False, "filename_pattern": None},
            "retain": None,
            "segments_folder": None,
        }
    }


def test_component_root_rejects_unknown_key_in_its_component() -> None:
    """Only the keys of other components are let through, not unknown keys."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CameraRoot.model_validate({"ffmpeg": {"host": "h", "prot": 1}})
