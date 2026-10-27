"""Convert Pydantic config models to the structure stored in config.json."""

from __future__ import annotations

import types
from typing import Annotated, Any, Literal, Union, get_args, get_origin

import annotated_types
from pydantic import BaseModel, RootModel, SecretStr
from pydantic.fields import FieldInfo

from viseron.helpers.config_model import MapKey, deprecation_warning
from viseron.helpers.config_types import OneOf
from viseron.helpers.validators import UNDEFINED

TYPES_MAP = {
    int: "integer",
    str: "string",
    SecretStr: "string",
    float: "float",
    bool: "boolean",
    list: "list",
    bytes: "bytes",
}


def convert_model(model: type[BaseModel]) -> list[dict[str, Any]]:
    """Convert a config model to the list of config options stored in config.json."""
    if issubclass(model, RootModel):
        root = model.model_fields["root"]
        converted = _convert_type(root.annotation, root.metadata)
        if not isinstance(converted, list):
            raise TypeError(f"Root of {model.__name__} is not a map")
        return converted
    return _convert_fields(model)


def _convert_fields(model: type[BaseModel]) -> list[dict[str, Any]]:
    """Return one docs entry per field of the model."""
    entries = []
    for name, field in model.model_fields.items():
        key = field.alias or name
        entry = _as_entry(_convert_type(field.annotation, field.metadata))

        if field.deprecated:
            entry["name"] = {
                "type": "deprecated",
                "name": key,
                "value": _deprecation_message(key, field),
            }
        else:
            entry["name"] = key
        entry["description"] = field.description

        if field.deprecated:
            entry["deprecated"] = True
        elif field.is_required():
            entry["required"] = True
        else:
            entry["optional"] = True
        entry["default"] = _default(field)
        entries.append(entry)
    return entries


def _deprecation_message(key: str, field: FieldInfo) -> str | None:
    """Return the message given to Field(deprecated=...), or a default one."""
    if isinstance(field.deprecated, bool):
        return deprecation_warning(key, field)
    return field.deprecation_message


def _default(field: FieldInfo) -> Any:
    """Return the default shown in the docs, None if there is none."""
    if field.is_required():
        return None
    default = field.get_default(call_default_factory=True)
    if isinstance(default, (BaseModel, UNDEFINED)):
        # The keys of a section show their own defaults, and UNDEFINED is no value
        return None
    return default


def _as_entry(converted: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap a list of entries in a map entry."""
    if isinstance(converted, list):
        return {"type": "map", "value": converted}
    return converted


def _unwrap(annotation: Any, metadata: Any = ()) -> tuple[Any, list[Any]]:
    """Split an annotation into its base type and all Annotated metadata.

    Metadata of inner Annotated layers comes before metadata of outer layers.
    """
    collected = list(metadata)
    while get_origin(annotation) is Annotated:
        annotation, *inner = get_args(annotation)
        collected = [*inner, *collected]
    return annotation, collected


def _convert_type(
    annotation: Any, metadata: Any = ()
) -> dict[str, Any] | list[dict[str, Any]]:
    """Convert a type to a docs fragment, or a list of entries if it is a map."""
    base, collected = _unwrap(annotation, metadata)
    converted = {} if base is Any else _convert_base(base)
    if isinstance(converted, list):
        return converted
    for item in collected:
        converted.update(_fragment(item))
    if not converted:
        raise ValueError(f"Unable to convert type: {annotation!r}")
    return converted


def _convert_base(base: Any) -> dict[str, Any] | list[dict[str, Any]]:
    """Convert a type without Annotated metadata."""
    origin = get_origin(base)

    if origin in (Union, types.UnionType):
        members = [member for member in get_args(base) if member is not type(None)]
        options = _flatten_options([_convert_type(member) for member in members])
        if len(options) == 1:
            return options[0]
        return {"type": "select", "options": options}

    if isinstance(base, type) and issubclass(base, BaseModel):
        return _convert_fields(base)

    if origin is dict:
        key_type, value_type = get_args(base)
        if value_type is Any:
            return []
        return [_convert_map_entry(key_type, value_type)]

    if origin is list:
        return {
            "type": "list",
            "values": [_convert_type(item) for item in get_args(base)],
        }

    if origin is Literal:
        return OneOf(get_args(base)).docs

    if base in TYPES_MAP:
        return {"type": TYPES_MAP[base]}

    raise ValueError(f"Unable to convert type: {base!r}")


def _convert_map_entry(key_type: Any, value_type: Any) -> dict[str, Any]:
    """Return the docs entry of a map with user defined keys."""
    entry = _as_entry(_convert_type(value_type))
    entry["name"] = _convert_type(key_type)

    description = None
    flag = None
    for item in _unwrap(key_type)[1]:
        if isinstance(item, MapKey):
            description = item.description or description
            flag = item.flag or flag
    entry["description"] = description
    if flag:
        entry[flag] = True
        entry["default"] = None
    return entry


def _flatten_options(options: list[Any]) -> list[Any]:
    """Lift the options of nested selects into one list."""
    flattened = []
    for option in options:
        if isinstance(option, dict) and "options" in option:
            flattened += _flatten_options(option["options"])
        else:
            flattened.append(option)
    return flattened


def _fragment(item: Any) -> dict[str, Any]:
    """Return the docs fragment that a metadata item contributes."""
    docs = getattr(item, "docs", None)
    if isinstance(docs, dict):
        return docs
    if isinstance(item, FieldInfo):
        fragment: dict[str, Any] = {}
        for nested in item.metadata:
            fragment.update(_fragment(nested))
        return fragment
    if isinstance(item, (annotated_types.Ge, annotated_types.Gt)):
        return {
            "valueMin": item.ge if isinstance(item, annotated_types.Ge) else item.gt
        }
    if isinstance(item, (annotated_types.Le, annotated_types.Lt)):
        return {
            "valueMax": item.le if isinstance(item, annotated_types.Le) else item.lt
        }
    if isinstance(item, annotated_types.MinLen):
        return {"lengthMin": item.min_length}
    if isinstance(item, annotated_types.MaxLen):
        return {"lengthMax": item.max_length}
    return {}
