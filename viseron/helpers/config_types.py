"""Reusable types for Pydantic config models."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Annotated, Any, TypeAlias, TypeVar
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from jinja2 import BaseLoader, Environment, TemplateError
from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    GetCoreSchemaHandler,
    SerializerFunctionWrapHandler,
    StringConstraints,
    WrapSerializer,
)
from pydantic_core import CoreSchema, PydanticCustomError, core_schema

from viseron.helpers import slugify
from viseron.helpers.config_model import ConfigModel, Docs, MapKey
from viseron.helpers.schemas import DESC_X, DESC_Y
from viseron.helpers.validators import UNDEFINED

if TYPE_CHECKING:
    from collections.abc import Iterable

T = TypeVar("T")


class OneOf:
    """Require the value to be one of the given options.

    Put it in the metadata of an Annotated type. Use it when the options are
    defined at runtime, otherwise a Literal is the better choice.
    """

    def __init__(self, options: Iterable[Any]) -> None:
        self.options = tuple(options)

    def __get_pydantic_core_schema__(
        self, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Validate the value as source_type first, then check the options."""
        return core_schema.no_info_after_validator_function(
            self._validate, handler(source_type)
        )

    def _validate(self, value: Any) -> Any:
        if value not in self.options:
            raise PydanticCustomError(
                "one_of",
                "Input should be one of {options}",
                {"options": ", ".join(repr(option) for option in self.options)},
            )
        return value

    @property
    def docs(self) -> dict[str, Any]:
        """Return the docs fragment read by scripts/gen_docs."""
        return {
            "type": "select",
            "options": [
                {"type": "none", "value": "null"}
                if option is None
                else {"type": "constant", "value": option}
                for option in self.options
            ],
        }


def _serialize_undefinable(value: Any, handler: SerializerFunctionWrapHandler) -> Any:
    return value if isinstance(value, UNDEFINED) else handler(value)


if TYPE_CHECKING:
    Undefinable: TypeAlias = T | UNDEFINED
else:

    class Undefinable:
        """The type T, or UNDEFINED when the key is not set in the config.

        Use it when the code has to tell a key that is not set apart from an
        explicit null, and give the field the default UNDEFINED:

            tiers: Undefinable[list[Tier] | None] = Field(default_factory=UNDEFINED)

        UNDEFINED is only part of the type that type checkers see. The config is
        validated as T, since the sentinel can not be written in a config.
        """

        def __class_getitem__(cls, item: Any) -> Any:
            """Return item, with a serializer that lets UNDEFINED through."""
            return Annotated[item, WrapSerializer(_serialize_undefinable)]


def _none_to_dict(value: Any) -> Any:
    return {} if value is None else value


def _slug(value: str) -> str:
    slugified = slugify(value)
    if value and value == slugified:
        return value
    if slugified:
        raise PydanticCustomError(
            "slug",
            "Input should be a valid slug, for example '{example}'",
            {"example": slugified},
        )
    raise PydanticCustomError("slug", "Input should be a valid slug")


def _cron_expression(value: str) -> str:
    if not croniter.is_valid(value):
        raise PydanticCustomError(
            "cron_expression", "Input should be a valid cron expression"
        )
    return value


def _timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        # ZoneInfo raises ZoneInfoNotFoundError for unknown zones, but a
        # plain ValueError for empty, absolute or non-normalized keys.
        raise PydanticCustomError(
            "timezone", "Input should be a valid timezone"
        ) from error
    return value


def _jinja2_template(value: str) -> str:
    env = Environment(loader=BaseLoader(), autoescape=True)
    try:
        env.compile(value)
    except TemplateError as error:
        raise PydanticCustomError(
            "jinja2_template",
            "Input should be a valid Jinja2 template, {error}",
            {"error": str(error)},
        ) from error
    return value


def _url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise PydanticCustomError("url", "Input should be a valid URL")
    return value


def _existing_path(value: str) -> str:
    if not os.path.exists(value):
        raise PydanticCustomError("existing_path", "Path does not exist")
    return value


# Use as Annotated[SomeType, NoneToDict] so that a section that is set to null,
# like "recorder:" without any keys, is validated as an empty section.
NoneToDict = BeforeValidator(_none_to_dict)  # pylint: disable=invalid-name

Lower = Annotated[str, StringConstraints(to_lower=True), Docs(lower=True)]

Slug = Annotated[str, AfterValidator(_slug)]

CameraIdentifier = Annotated[
    Slug,
    Docs(type="CAMERA_IDENTIFIER"),
    MapKey(
        description=(
            "Camera identifier. "
            "Valid characters are lowercase a-z, numbers and underscores."
        ),
        flag="cameraidentifier",
    ),
]

CronExpression = Annotated[str, AfterValidator(_cron_expression)]

Timezone = Annotated[str, AfterValidator(_timezone)]

Jinja2Template = Annotated[
    str,
    AfterValidator(_jinja2_template),
    Docs(type="jinja2_template", value="jinja2_template"),
]

Url = Annotated[str, AfterValidator(_url), Docs(format="url")]

ExistingPath = Annotated[str, AfterValidator(_existing_path), Docs(format="file path")]

FloatZeroToOne = Annotated[float, Field(ge=0.0, le=1.0)]

FloatMinZero = Annotated[float, Field(ge=0.0)]


class Coordinate(ConfigModel):
    """A point in an image."""

    x: int = Field(description=DESC_X)
    y: int = Field(description=DESC_Y)


Coordinates = Annotated[list[Coordinate], Field(min_length=3)]
