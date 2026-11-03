"""Tests for validating config with Pydantic models and Voluptuous schemas."""

from __future__ import annotations

import pytest
import voluptuous as vol
from pydantic import BaseModel, ConfigDict, Field

from viseron.helpers.config_validation import ConfigValidationError, validate_config


class Stream(BaseModel):
    """Nested model used in the tests."""

    model_config = ConfigDict(extra="forbid")

    path: str
    port: int = 554


class Camera(BaseModel):
    """Model used in the tests."""

    model_config = ConfigDict(extra="forbid")

    host: str
    stream: Stream = Field(default_factory=lambda: Stream(path="/"))
    streams: list[Stream] = Field(default_factory=list)


VOLUPTUOUS_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Optional("port", default=554): int,
    }
)


def test_voluptuous_schema_returns_validated_dict() -> None:
    """A Voluptuous schema is called, so its defaults are applied."""
    assert validate_config(VOLUPTUOUS_SCHEMA, {"host": "h"}) == {
        "host": "h",
        "port": 554,
    }


def test_voluptuous_schema_error_is_humanized() -> None:
    """A Voluptuous error is formatted with humanize_error."""
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config(VOLUPTUOUS_SCHEMA, {"host": "h", "port": "abc"})
    assert (
        str(excinfo.value)
        == "expected int for dictionary value @ data['port']. Got 'abc'"
    )


def test_model_returns_the_model() -> None:
    """A model is validated and returned as it is, for typed access."""
    camera = validate_config(Camera, {"host": "h", "stream": {"path": "/live"}})
    assert isinstance(camera, Camera)
    assert camera.stream.path == "/live"
    assert camera.stream.port == 554


def test_other_exceptions_are_not_wrapped() -> None:
    """Only validation errors become ConfigValidationError."""

    def schema(_config: object) -> object:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        validate_config(schema, {})


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            {"host": "h", "stream": {"path": "/", "port": "abc"}},
            "stream.port: Input should be a valid integer, unable to parse string "
            "as an integer",
            id="nested_key",
        ),
        pytest.param(
            {"host": "h", "streams": [{"path": "/a"}, {"path": 5}]},
            "streams.1.path: Input should be a valid string",
            id="list_index",
        ),
        pytest.param({}, "host: Field required", id="missing_key"),
        pytest.param(
            {"host": "h", "prot": 1},
            "prot: Extra inputs are not permitted",
            id="unknown_key",
        ),
        pytest.param(
            {"host": {"password": "hunter2"}},
            "host: Input should be a valid string",
            id="value_is_not_shown",
        ),
        pytest.param(
            {"stream": {"port": "abc"}},
            "host: Field required\n"
            "stream.path: Field required\n"
            "stream.port: Input should be a valid integer, unable to parse string "
            "as an integer",
            id="one_line_per_error",
        ),
        pytest.param(
            "host",
            "Input should be a valid dictionary or instance of Camera",
            id="error_for_the_whole_config_has_no_path",
        ),
    ],
)
def test_model_error(config: object, expected: str) -> None:
    """A model error names the path to each key and what is wrong with it."""
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config(Camera, config)
    assert str(excinfo.value) == expected
