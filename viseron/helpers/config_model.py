"""Base classes for Pydantic config models."""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator
from typing_extensions import Self

if TYPE_CHECKING:
    from collections.abc import ItemsView, KeysView, ValuesView

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


class LegacyConfigAccessWarning(DeprecationWarning):
    """A config model is read like a dict, by code that still has to be converted."""


@cache
def _fields_by_key(model: type[BaseModel]) -> dict[str, str]:
    """Return the name of the field for each key as it is written in the config."""
    return {field.alias or name: name for name, field in model.model_fields.items()}


class ConfigModel(BaseModel):
    """Base class for all config models.

    Unknown keys are rejected, so that a misspelled key is not silently ignored.
    Validation errors do not show the value that was given, since their text ends
    up in logs and the value can be a secret.

    A model can also be read like the config dict it replaces, with config[key],
    config.get(key), key in config, keys(), values() and items(). This keeps code
    working that is not converted to attribute access yet. Each such read emits a
    LegacyConfigAccessWarning at the line that reads. An optional key that is not
    set counts as absent, like it was in the dict. Remove this together with the
    warning when no reader is left.
    """

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    @model_validator(mode="after")
    def _warn_about_deprecated_keys(self) -> Self:
        """Log a warning for each deprecated key that is set in the config."""
        for name, field in type(self).model_fields.items():
            if field.deprecated and name in self.model_fields_set:
                LOGGER.warning(deprecation_warning(field.alias or name, field))
        return self

    def __getitem__(self, key: str) -> Any:
        """Return the value of a key."""
        self._warn_about_legacy_access()
        # Read from __dict__, as getattr warns when the key is deprecated
        return self.__dict__[_fields_by_key(type(self))[key]]

    def __contains__(self, key: str) -> bool:
        """Return if a key is present."""
        self._warn_about_legacy_access()
        return self._has_key(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value of a key, or default if the key is absent."""
        self._warn_about_legacy_access()
        if self._has_key(key):
            return self.__dict__[_fields_by_key(type(self))[key]]
        return default

    def keys(self) -> KeysView[str]:
        """Return the keys that are present."""
        self._warn_about_legacy_access()
        return self._legacy_items().keys()

    def values(self) -> ValuesView[Any]:
        """Return the values of the keys that are present."""
        self._warn_about_legacy_access()
        return self._legacy_items().values()

    def items(self) -> ItemsView[str, Any]:
        """Return the keys that are present and their values."""
        self._warn_about_legacy_access()
        return self._legacy_items().items()

    def _has_key(self, key: str) -> bool:
        """Return if the config dict would have held the key."""
        name = _fields_by_key(type(self)).get(key)
        return name is not None and (
            self.__dict__[name] is not None or name in self.model_fields_set
        )

    def _legacy_items(self) -> dict[str, Any]:
        """Return the keys and values that the config dict would have held."""
        return {
            key: self.__dict__[name]
            for key, name in _fields_by_key(type(self)).items()
            if self._has_key(key)
        }

    def _warn_about_legacy_access(self) -> None:
        warnings.warn(
            f"{type(self).__name__} is read like a dict, use attribute access instead",
            LegacyConfigAccessWarning,
            stacklevel=3,
        )


class ComponentRoot(ConfigModel):
    """Base class for the root model of a component, exported as CONFIG_SCHEMA.

    The root model is validated against the whole config, so the keys of all other
    components are ignored.
    """

    model_config = ConfigDict(extra="ignore")
