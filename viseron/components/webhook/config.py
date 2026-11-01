"""Config of the webhook component."""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_core import PydanticCustomError

from viseron.helpers.config_model import ComponentRoot, ConfigModel, MapKey
from viseron.helpers.config_types import (
    Jinja2Template,
    Lower,
    NoneToDict,
    OneOf,
    SecretJinja2Template,
    Slug,
)

from .const import (
    DEFAULT_CONTENT_TYPE,
    DEFAULT_METHOD,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DESC_CA_CERT,
    DESC_COMPONENT,
    DESC_CONDITION,
    DESC_CONTENT_TYPE,
    DESC_EVENT,
    DESC_HEADER,
    DESC_HEADERS,
    DESC_HOOK,
    DESC_METHOD,
    DESC_PASSWORD,
    DESC_PAYLOAD,
    DESC_TIMEOUT,
    DESC_TRIGGER,
    DESC_URL,
    DESC_USERNAME,
    DESC_VERIFY_SSL,
    MESSAGE_AUTHENTICATION,
    SUPPORTED_METHODS,
)

Method = Annotated[Lower, OneOf(SUPPORTED_METHODS)]

HookName = Annotated[Slug, MapKey(description=DESC_HOOK)]

HeaderName = Annotated[str, MapKey(description=DESC_HEADER)]


class TriggerConfig(ConfigModel):
    """Config of the event that triggers a hook."""

    event: str = Field(description=DESC_EVENT)
    condition: Jinja2Template | None = Field(default=None, description=DESC_CONDITION)


class HookConfig(ConfigModel):
    """Config of a hook."""

    trigger: TriggerConfig = Field(description=DESC_TRIGGER)
    url: Jinja2Template | None = Field(description=DESC_URL)
    method: Method = Field(default=DEFAULT_METHOD, description=DESC_METHOD)
    headers: Annotated[dict[HeaderName, SecretJinja2Template], NoneToDict] = Field(
        default_factory=dict, description=DESC_HEADERS
    )
    username: str | None = Field(default=None, description=DESC_USERNAME)
    password: SecretStr | None = Field(default=None, description=DESC_PASSWORD)
    payload: Jinja2Template | None = Field(default=None, description=DESC_PAYLOAD)
    timeout: int = Field(default=DEFAULT_TIMEOUT, description=DESC_TIMEOUT)
    content_type: str = Field(
        default=DEFAULT_CONTENT_TYPE, description=DESC_CONTENT_TYPE
    )
    verify_ssl: bool = Field(default=DEFAULT_VERIFY_SSL, description=DESC_VERIFY_SSL)
    ca_cert: str | None = Field(default=None, description=DESC_CA_CERT)

    @model_validator(mode="after")
    def _check_authentication(self) -> Self:
        if (self.username is None) != (self.password is None):
            raise PydanticCustomError("authentication", MESSAGE_AUTHENTICATION)
        return self


class WebhookRoot(ComponentRoot):
    """Config with the webhook component at the root."""

    webhook: dict[HookName, HookConfig] = Field(description=DESC_COMPONENT)
