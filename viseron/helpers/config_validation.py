"""Validate config with either a Pydantic model or a Voluptuous schema."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from pydantic import BaseModel, ValidationError
from voluptuous.humanize import humanize_error

from viseron.exceptions import ViseronError


class ConfigValidationError(ViseronError):
    """Config failed validation. The message is meant to be shown to the user."""


def validate_config(schema: Any, config: Any) -> Any:
    """Validate config and return the validated config.

    A Pydantic model class returns an instance of the model. A Voluptuous schema
    returns a dict, and is accepted so that schemas can be ported one at a time.
    """
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        try:
            return schema.model_validate(config)
        except ValidationError as error:
            raise ConfigValidationError(format_validation_error(error)) from error

    try:
        return schema(config)
    except vol.Invalid as error:
        raise ConfigValidationError(humanize_error(config, error)) from error


def format_validation_error(error: ValidationError) -> str:
    """Return one line per error, as the path to the key and what is wrong with it.

    The value that was given is left out, since it can be a secret.
    """
    lines = []
    for details in error.errors(
        include_url=False, include_context=False, include_input=False
    ):
        path = ".".join(str(part) for part in details["loc"])
        lines.append(f"{path}: {details['msg']}" if path else details["msg"])
    return "\n".join(lines)
