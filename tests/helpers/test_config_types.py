"""Tests for the reusable config types."""

from __future__ import annotations

import re
from typing import Annotated, Any

import pytest
from pydantic import TypeAdapter, ValidationError

from viseron.helpers.config_types import (
    CameraIdentifier,
    Coordinates,
    CronExpression,
    ExistingPath,
    FloatMinZero,
    FloatZeroToOne,
    Jinja2Template,
    Lower,
    NoneToDict,
    OneOf,
    Slug,
    Timezone,
    Url,
)

Level = Annotated[Lower, OneOf({"info": 20, "debug": 10})]
NullableOption = Annotated[Any, OneOf([None, "a", 1])]
Section = Annotated[dict[str, int], NoneToDict]

TRIANGLE = [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 5, "y": 5}]

ACCEPTED: list[tuple[str, Any, Any, Any]] = [
    ("Lower", Lower, "DEBUG", "debug"),
    ("OneOf", Level, "INFO", "info"),
    ("OneOf", NullableOption, None, None),
    ("OneOf", NullableOption, 1, 1),
    ("NoneToDict", Section, None, {}),
    ("NoneToDict", Section, {"a": 1}, {"a": 1}),
    ("Slug", Slug, "my_stream", "my_stream"),
    ("CameraIdentifier", CameraIdentifier, "camera_1", "camera_1"),
    ("CronExpression", CronExpression, "0 8 * * mon-fri", "0 8 * * mon-fri"),
    ("Timezone", Timezone, "Europe/Stockholm", "Europe/Stockholm"),
    ("Jinja2Template", Jinja2Template, "{{ a }}", "{{ a }}"),
    ("Url", Url, "http://example.com/x", "http://example.com/x"),
    ("ExistingPath", ExistingPath, "/", "/"),
    ("FloatZeroToOne", FloatZeroToOne, 0.5, 0.5),
    ("FloatZeroToOne", FloatZeroToOne, 0, 0.0),
    ("FloatZeroToOne", FloatZeroToOne, 1, 1.0),
    ("FloatMinZero", FloatMinZero, 3, 3.0),
    ("Coordinates", Coordinates, TRIANGLE, TRIANGLE),
]

REJECTED: list[tuple[str, Any, Any]] = [
    ("Lower", Lower, 5),
    ("Lower", Lower, None),
    ("OneOf", Level, "verbose"),
    ("OneOf", NullableOption, "b"),
    ("OneOf", NullableOption, ["a"]),
    ("NoneToDict", Section, "a"),
    ("Slug", Slug, "My Stream"),
    ("Slug", Slug, ""),
    ("Slug", Slug, 5),
    ("Slug", Slug, None),
    ("CameraIdentifier", CameraIdentifier, "Camera 1"),
    ("CameraIdentifier", CameraIdentifier, ""),
    ("CameraIdentifier", CameraIdentifier, 1),
    ("CronExpression", CronExpression, "not cron"),
    ("CronExpression", CronExpression, 5),
    ("Timezone", Timezone, "Not/AZone"),
    ("Timezone", Timezone, ""),
    ("Timezone", Timezone, 5),
    ("Jinja2Template", Jinja2Template, "{{ a"),
    ("Jinja2Template", Jinja2Template, 5),
    ("Url", Url, "example.com"),
    ("Url", Url, 5),
    ("ExistingPath", ExistingPath, "/does/not/exist"),
    ("ExistingPath", ExistingPath, ""),
    ("FloatZeroToOne", FloatZeroToOne, 1.1),
    ("FloatZeroToOne", FloatZeroToOne, -0.1),
    ("FloatZeroToOne", FloatZeroToOne, float("nan")),
    ("FloatMinZero", FloatMinZero, -1),
    ("Coordinates", Coordinates, TRIANGLE[:2]),
    ("Coordinates", Coordinates, [{"x": 0}, *TRIANGLE]),
    ("Coordinates", Coordinates, [{"x": 0, "y": 0, "z": 0}, *TRIANGLE]),
]


@pytest.mark.parametrize(
    ("type_", "value", "expected"),
    [pytest.param(*case[1:], id=f"{case[0]}-{case[2]!r}") for case in ACCEPTED],
)
def test_config_type_accepts(type_: Any, value: Any, expected: Any) -> None:
    """Each type accepts a valid value and converts it."""
    adapter = TypeAdapter(type_)
    result = adapter.dump_python(adapter.validate_python(value))
    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize(
    ("type_", "value"),
    [pytest.param(*case[1:], id=f"{case[0]}-{case[2]!r}") for case in REJECTED],
)
def test_config_type_rejects(type_: Any, value: Any) -> None:
    """Each type rejects a value that is not valid."""
    with pytest.raises(ValidationError):
        TypeAdapter(type_).validate_python(value)


@pytest.mark.parametrize(
    ("type_", "value", "message"),
    [
        pytest.param(
            Level,
            "verbose",
            "Input should be one of 'info', 'debug'",
            id="OneOf",
        ),
        pytest.param(
            Slug,
            "My Stream",
            "Input should be a valid slug, for example 'my_stream'",
            id="Slug",
        ),
        pytest.param(
            Slug,
            "!",
            "Input should be a valid slug [type=slug",
            id="Slug-without_example",
        ),
        pytest.param(
            CronExpression,
            "not cron",
            "Input should be a valid cron expression",
            id="CronExpression",
        ),
        pytest.param(
            Timezone, "Not/AZone", "Input should be a valid timezone", id="Timezone"
        ),
        pytest.param(
            Jinja2Template,
            "{{ a",
            "Input should be a valid Jinja2 template, unexpected end of template",
            id="Jinja2Template",
        ),
        pytest.param(Url, "example.com", "Input should be a valid URL", id="Url"),
        pytest.param(
            ExistingPath, "/does/not/exist", "Path does not exist", id="ExistingPath"
        ),
    ],
)
def test_config_type_error_message(type_: Any, value: Any, message: str) -> None:
    """The error tells what is expected, without the prefix of a plain ValueError."""
    with pytest.raises(ValidationError, match=re.escape(message)) as excinfo:
        TypeAdapter(type_).validate_python(value)
    assert "Value error" not in str(excinfo.value)


def test_one_of_keeps_its_options() -> None:
    """Options given as an iterator can be validated against more than once."""
    adapter = TypeAdapter(Annotated[str, OneOf(iter(["a", "b"]))])
    assert adapter.validate_python("b") == "b"
    assert adapter.validate_python("a") == "a"


def test_one_of_docs() -> None:
    """The docs fragment lists the options, with null as its own type."""
    assert OneOf([None, "a", 1]).docs == {
        "type": "select",
        "options": [
            {"type": "none", "value": "null"},
            {"type": "constant", "value": "a"},
            {"type": "constant", "value": 1},
        ],
    }
