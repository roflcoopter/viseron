"""Tests for converting config models to the docs config.json structure."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

import pytest
from pydantic import Field, RootModel
from scripts.gen_docs.model_docs import convert_model

from viseron.helpers.config_model import ComponentRoot, ConfigModel, MapKey
from viseron.helpers.config_types import (
    CameraIdentifier,
    FloatZeroToOne,
    Lower,
    NoneToDict,
    OneOf,
    Slug,
    Undefinable,
)
from viseron.helpers.validators import UNDEFINED

Level = Annotated[Lower, OneOf(["info", "debug"])]
LoggerName = Annotated[str, MapKey(description="Logger name.", flag="required")]
StreamName = Annotated[Slug, MapKey(description="Stream name.")]

LEVEL_OPTIONS = [
    {"type": "constant", "value": "info"},
    {"type": "constant", "value": "debug"},
]


class Tier(ConfigModel):
    """Nested model used in a list."""

    path: str = Field(description="Path.")


class Stream(ConfigModel):
    """Nested model used as a section."""

    width: int = Field(default=640, description="Width.")


class Options(ConfigModel):
    """Model with one field per kind of key."""

    host: str = Field(description="Host.")
    port: int = Field(default=554, description="Port.", ge=1, le=65535)
    codec: str | None = Field(default=None, description="Codec.")
    stream: Stream = Field(default_factory=Stream, description="Stream.")
    tiers: Undefinable[list[Tier] | None] = Field(
        default_factory=UNDEFINED, description="Tiers."
    )
    retain: int | None = Field(
        default=None, description="Retain.", deprecated="Use tiers instead."
    )
    folder: str | None = Field(default=None, description="Folder.", deprecated=True)
    model_config_: str = Field(
        default="model.cfg", alias="model_config", description="Model config."
    )
    args: list[str] = Field(default_factory=list, description="Args.")


STREAM_MAP = {
    "type": "map",
    "value": [
        {
            "type": "integer",
            "name": "width",
            "description": "Width.",
            "optional": True,
            "default": 640,
        }
    ],
}


def _entry(annotation: Any, **field_kwargs: Any) -> dict[str, Any]:
    """Return the docs entry of a single optional field with the given type."""

    class Model(ConfigModel):
        """Model with one field."""

        option: annotation = Field(default=None, description="Option.", **field_kwargs)

    (entry,) = convert_model(Model)
    assert entry.pop("name") == "option"
    assert entry.pop("description") == "Option."
    assert entry.pop("optional") is True
    assert entry.pop("default") is None
    return entry


def test_kinds_of_keys() -> None:
    """Each kind of key gets its flag, name and default."""
    assert convert_model(Options) == [
        {
            "type": "string",
            "name": "host",
            "description": "Host.",
            "required": True,
            "default": None,
        },
        {
            "type": "integer",
            "valueMin": 1,
            "valueMax": 65535,
            "name": "port",
            "description": "Port.",
            "optional": True,
            "default": 554,
        },
        {
            "type": "string",
            "name": "codec",
            "description": "Codec.",
            "optional": True,
            "default": None,
        },
        {
            **STREAM_MAP,
            "name": "stream",
            "description": "Stream.",
            "optional": True,
            "default": None,
        },
        {
            "type": "list",
            "values": [
                [
                    {
                        "type": "string",
                        "name": "path",
                        "description": "Path.",
                        "required": True,
                        "default": None,
                    }
                ]
            ],
            "name": "tiers",
            "description": "Tiers.",
            "optional": True,
            "default": None,
        },
        {
            "type": "integer",
            "name": {
                "type": "deprecated",
                "name": "retain",
                "value": "Use tiers instead.",
            },
            "description": "Retain.",
            "deprecated": True,
            "default": None,
        },
        {
            "type": "string",
            "name": {
                "type": "deprecated",
                "name": "folder",
                "value": "Config option 'folder' is deprecated and will be removed "
                "in a future version.",
            },
            "description": "Folder.",
            "deprecated": True,
            "default": None,
        },
        {
            "type": "string",
            "name": "model_config",
            "description": "Model config.",
            "optional": True,
            "default": "model.cfg",
        },
        {
            "type": "list",
            "values": [{"type": "string"}],
            "name": "args",
            "description": "Args.",
            "optional": True,
            "default": [],
        },
    ]


def test_converted_model_is_json() -> None:
    """The result can be written to config.json, also with a section as default."""
    assert json.loads(json.dumps(convert_model(Options))) == convert_model(Options)


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        pytest.param(Stream, STREAM_MAP, id="nested_model"),
        pytest.param(
            Annotated[Stream, NoneToDict], STREAM_MAP, id="nested_model_with_metadata"
        ),
        pytest.param(Stream | None, STREAM_MAP, id="nullable_nested_model"),
        pytest.param(
            int | list[str] | None,
            {
                "type": "select",
                "options": [
                    {"type": "integer"},
                    {"type": "list", "values": [{"type": "string"}]},
                ],
            },
            id="union_without_the_null_member",
        ),
        pytest.param(
            Literal["a", "b"] | int,
            {
                "type": "select",
                "options": [
                    {"type": "constant", "value": "a"},
                    {"type": "constant", "value": "b"},
                    {"type": "integer"},
                ],
            },
            id="select_in_union_is_flattened",
        ),
        pytest.param(
            Level,
            {"type": "select", "lower": True, "options": LEVEL_OPTIONS},
            id="docs_fragments_are_merged",
        ),
        pytest.param(
            Annotated[Any, OneOf([None, 1])],
            {
                "type": "select",
                "options": [
                    {"type": "none", "value": "null"},
                    {"type": "constant", "value": 1},
                ],
            },
            id="any_with_options",
        ),
        pytest.param(
            FloatZeroToOne,
            {"type": "float", "valueMin": 0.0, "valueMax": 1.0},
            id="range",
        ),
        pytest.param(
            Annotated[list[str], Field(min_length=1, max_length=5)],
            {
                "type": "list",
                "values": [{"type": "string"}],
                "lengthMin": 1,
                "lengthMax": 5,
            },
            id="length",
        ),
        pytest.param(
            dict[LoggerName, Level],
            {
                "type": "map",
                "value": [
                    {
                        "type": "select",
                        "lower": True,
                        "options": LEVEL_OPTIONS,
                        "name": {"type": "string"},
                        "description": "Logger name.",
                        "required": True,
                        "default": None,
                    }
                ],
            },
            id="map_with_flagged_key",
        ),
        pytest.param(
            dict[StreamName, int],
            {
                "type": "map",
                "value": [
                    {
                        "type": "integer",
                        "name": {"type": "string"},
                        "description": "Stream name.",
                    }
                ],
            },
            id="map_with_key_without_flag",
        ),
        pytest.param(dict[str, Any], {"type": "map", "value": []}, id="free_form_map"),
    ],
)
def test_type(annotation: Any, expected: dict[str, Any]) -> None:
    """Each kind of type is converted to its docs entry."""
    assert _entry(annotation) == expected


def test_map_with_camera_identifier_keys() -> None:
    """Camera identifier keys keep their flag when the description is overridden."""
    key = Annotated[CameraIdentifier, MapKey(description="The camera.")]
    (default,) = _entry(dict[CameraIdentifier, Stream])["value"]
    (overridden,) = _entry(dict[key, Stream])["value"]

    assert default["name"] == {"type": "CAMERA_IDENTIFIER"}
    assert default["description"] == (
        "Camera identifier. "
        "Valid characters are lowercase a-z, numbers and underscores."
    )
    assert default["cameraidentifier"] is True
    assert default["default"] is None
    assert default["type"] == "map"

    assert overridden["description"] == "The camera."
    assert overridden["cameraidentifier"] is True


def test_component_root() -> None:
    """The root model of a component is one required map."""

    class Root(ComponentRoot):
        """Root model."""

        stream: Stream = Field(description="Stream.")

    assert convert_model(Root) == [
        {
            **STREAM_MAP,
            "name": "stream",
            "description": "Stream.",
            "required": True,
            "default": None,
        }
    ]


def test_root_model_with_user_defined_keys() -> None:
    """A RootModel that is a map is converted like a map."""

    class Cameras(RootModel[dict[CameraIdentifier, Stream]]):
        """Root model."""

    (entry,) = convert_model(Cameras)
    assert entry["name"] == {"type": "CAMERA_IDENTIFIER"}
    assert entry["cameraidentifier"] is True


def test_root_model_that_is_not_a_map_is_an_error() -> None:
    """Only maps are supported at the root."""

    class Numbers(RootModel[list[int]]):
        """Root model."""

    with pytest.raises(TypeError, match="Root of Numbers is not a map"):
        convert_model(Numbers)


@pytest.mark.parametrize(
    "annotation",
    [
        pytest.param(set[str], id="unknown_type"),
        pytest.param(Any, id="any_without_docs"),
    ],
)
def test_type_that_can_not_be_documented_is_an_error(annotation: Any) -> None:
    """A type the converter does not know fails loudly instead of guessing."""
    with pytest.raises(ValueError, match="Unable to convert type"):
        _entry(annotation)
