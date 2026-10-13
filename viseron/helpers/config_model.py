"""Base classes for Pydantic config models."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator
from typing_extensions import Self

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

LOGGER = logging.getLogger(__name__)


class Docs:
    """Docs fragment for a config option, read by scripts/gen_docs.

    Put it in the metadata of an Annotated type. The keyword arguments are merged
    into the generated docs entry of every config option that uses the type.
    """

    def __init__(self, **docs: Any) -> None:
        self.docs = docs


@dataclass(frozen=True)
class MapKey:
    """Docs for the key of a map with user defined keys, read by scripts/gen_docs.

    Put it in the metadata of the Annotated key type.
    flag is added to the docs entry as "<flag>: true", for example "required".
    """

    description: str | None = None
    flag: str | None = None


def deprecation_warning(key: str, field: FieldInfo) -> str:
    """Return the warning to show for a key declared with Field(deprecated=...)."""
    warning = (
        f"Config option '{key}' is deprecated and will be removed in a future version."
    )
    if isinstance(field.deprecated, bool):
        return warning
    return f"{warning} {field.deprecation_message}"


class ConfigModel(BaseModel):
    """Base class for all config models.

    Unknown keys are rejected, so that a misspelled key is not silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _warn_about_deprecated_keys(self) -> Self:
        """Log a warning for each deprecated key that is set in the config."""
        for name, field in type(self).model_fields.items():
            if field.deprecated and name in self.model_fields_set:
                LOGGER.warning(deprecation_warning(field.alias or name, field))
        return self


class ComponentRoot(ConfigModel):
    """Base class for the root model of a component, exported as CONFIG_SCHEMA.

    The root model is validated against the whole config, so the keys of all other
    components are ignored.
    """

    model_config = ConfigDict(extra="ignore")
