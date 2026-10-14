"""Tests for the config model base classes."""

from __future__ import annotations

import copy
import logging
import warnings
from functools import reduce
from operator import getitem
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import Field, ValidationError

from viseron.helpers.config_model import (
    ComponentRoot,
    ConfigModel,
    LegacyConfigAccessWarning,
)

if TYPE_CHECKING:
    from collections.abc import Callable

IGNORE_LEGACY_ACCESS = "ignore::viseron.helpers.config_model.LegacyConfigAccessWarning"


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


class Recorder(ConfigModel):
    """Section that is read like a dict in the tests."""

    lookback: int = 5
    codec: str | None = None
    model_config_: str = Field(default="model.cfg", alias="model_config")


class Nvr(ConfigModel):
    """Model with a nested section and a map, read like a dict in the tests."""

    recorder: Recorder = Field(default_factory=Recorder)
    labels: dict[str, int] = Field(default_factory=dict)


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


@pytest.mark.filterwarnings(IGNORE_LEGACY_ACCESS)
@pytest.mark.parametrize(
    ("keys", "expected"),
    [
        pytest.param(("recorder", "lookback"), 7, id="nested_section"),
        pytest.param(("recorder", "model_config"), "model.cfg", id="alias"),
        pytest.param(("recorder", "codec"), None, id="optional_key_that_is_not_set"),
        pytest.param(("labels", "person"), 1, id="map_is_a_plain_dict"),
    ],
)
def test_dict_style_read(keys: tuple[str, ...], expected: Any) -> None:
    """A model can be subscripted like the config dict it replaces."""
    config = Nvr.model_validate({"recorder": {"lookback": 7}, "labels": {"person": 1}})
    assert reduce(getitem, keys, config) == expected


@pytest.mark.filterwarnings(IGNORE_LEGACY_ACCESS)
@pytest.mark.parametrize(
    "key",
    [
        pytest.param("lokback", id="unknown_key"),
        pytest.param("model_config_", id="field_name_of_an_aliased_key"),
    ],
)
def test_dict_style_read_of_missing_key_raises(key: str) -> None:
    """Only the keys as they are written in the config can be subscripted."""
    with pytest.raises(KeyError):
        Recorder()[key]  # pylint: disable=expression-not-assigned


@pytest.mark.filterwarnings(IGNORE_LEGACY_ACCESS)
@pytest.mark.parametrize(
    ("config", "key", "expected"),
    [
        pytest.param({}, "lookback", True, id="key_with_default"),
        pytest.param({}, "codec", False, id="optional_key_that_is_not_set"),
        pytest.param({"codec": "h264"}, "codec", True, id="optional_key_that_is_set"),
        pytest.param({"codec": None}, "codec", True, id="optional_key_set_to_null"),
        pytest.param({}, "lokback", False, id="unknown_key"),
    ],
)
def test_dict_style_contains(config: dict, key: str, expected: bool) -> None:
    """An optional key that is not set is absent, like it was in the config dict."""
    assert (key in Recorder.model_validate(config)) is expected


@pytest.mark.filterwarnings(IGNORE_LEGACY_ACCESS)
@pytest.mark.parametrize(
    ("config", "key", "expected"),
    [
        pytest.param({}, "lookback", 5, id="key_with_default"),
        pytest.param({}, "codec", "fallback", id="optional_key_that_is_not_set"),
        pytest.param({"codec": "h264"}, "codec", "h264", id="optional_key_that_is_set"),
        pytest.param({"codec": None}, "codec", None, id="optional_key_set_to_null"),
        pytest.param({}, "lokback", "fallback", id="unknown_key"),
    ],
)
def test_dict_style_get(config: dict, key: str, expected: Any) -> None:
    """The default given to get is only returned for a key that is absent."""
    assert Recorder.model_validate(config).get(key, "fallback") == expected


@pytest.mark.filterwarnings(IGNORE_LEGACY_ACCESS)
def test_dict_style_get_defaults_to_none() -> None:
    """Without a default, get returns None for a key that is absent."""
    assert Recorder().get("codec") is None


@pytest.mark.filterwarnings(IGNORE_LEGACY_ACCESS)
def test_dict_style_keys_values_and_items() -> None:
    """Only the keys that are present are listed, by their name in the config."""
    recorder = Recorder()
    assert list(recorder.keys()) == ["lookback", "model_config"]
    assert list(recorder.values()) == [5, "model.cfg"]
    assert list(recorder.items()) == [("lookback", 5), ("model_config", "model.cfg")]


@pytest.mark.parametrize(
    "read",
    [
        pytest.param(lambda config: config["lookback"], id="subscript"),
        pytest.param(lambda config: config.get("lookback"), id="get"),
        pytest.param(lambda config: "lookback" in config, id="in"),
        pytest.param(lambda config: config.keys(), id="keys"),
        pytest.param(lambda config: config.values(), id="values"),
        pytest.param(lambda config: config.items(), id="items"),
    ],
)
def test_dict_style_read_warns_once_at_the_reader(
    read: Callable[[Recorder], Any],
) -> None:
    """Each dict-style read is reported once, at the line that is not converted."""
    with pytest.warns(LegacyConfigAccessWarning, match="Recorder") as caught:
        read(Recorder())
    assert [warning.filename for warning in caught] == [__file__]


def test_deprecated_key_can_be_read_like_a_dict() -> None:
    """A dict-style read of a deprecated key only reports the dict-style read."""
    camera = Camera.model_validate({"host": "h"})
    with pytest.warns(LegacyConfigAccessWarning) as caught:
        assert camera["retain"] is None
    assert len(caught) == 1


def test_model_does_not_use_dict_style_reads_itself() -> None:
    """Validating, reading attributes, comparing and copying does not warn."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", LegacyConfigAccessWarning)
        config = Nvr.model_validate({"recorder": {"lookback": 7}})
        assert config.recorder.lookback == 7
        assert config == Nvr(recorder=Recorder(lookback=7))
        assert copy.deepcopy(config).model_dump() == config.model_dump()
        assert "lookback=7" in repr(config)
