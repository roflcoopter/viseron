"""Webhook component."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import requests
import voluptuous as vol
from jinja2 import BaseLoader, Environment

from viseron.events import Event
from viseron.helpers.template import render_template, render_template_condition
from viseron.helpers.validators import (
    CoerceNoneToDict,
    Maybe,
    Slug,
    StringKey,
    jinja2_template,
)

from .const import (
    COMPONENT,
    CONFIG_CONDITION,
    CONFIG_CONTENT_TYPE,
    CONFIG_EVENT,
    CONFIG_HEADERS,
    CONFIG_METHOD,
    CONFIG_PASSWORD,
    CONFIG_PAYLOAD,
    CONFIG_TIMEOUT,
    CONFIG_TRIGGER,
    CONFIG_URL,
    CONFIG_USERNAME,
    CONFIG_VERIFY_SSL,
    DEFAULT_CONDITION,
    DEFAULT_CONTENT_TYPE,
    DEFAULT_HEADERS,
    DEFAULT_METHOD,
    DEFAULT_PASSWORD,
    DEFAULT_PAYLOAD,
    DEFAULT_TIMEOUT,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_SSL,
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
    INCLUSION_GROUP_AUTHENTICATION,
    MESSAGE_AUTHENTICATION,
    SUPPORTED_METHODS,
)

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

HOOK_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_TRIGGER, description=DESC_TRIGGER): {
            vol.Required(
                CONFIG_EVENT,
                description=DESC_EVENT,
            ): str,
            vol.Optional(
                CONFIG_CONDITION,
                default=DEFAULT_CONDITION,
                description=DESC_CONDITION,
            ): Maybe(jinja2_template),
        },
        vol.Required(
            CONFIG_URL,
            description=DESC_URL,
        ): Maybe(jinja2_template),
        vol.Optional(
            CONFIG_METHOD,
            description=DESC_METHOD,
            default=DEFAULT_METHOD,
        ): vol.All(vol.Lower, vol.In(SUPPORTED_METHODS)),
        vol.Optional(
            CONFIG_HEADERS,
            default=DEFAULT_HEADERS,
            description=DESC_HEADERS,
        ): vol.All(
            CoerceNoneToDict(),
            {StringKey(description=DESC_HEADER): jinja2_template},
        ),
        vol.Inclusive(
            CONFIG_USERNAME,
            INCLUSION_GROUP_AUTHENTICATION,
            default=DEFAULT_USERNAME,
            description=DESC_USERNAME,
            msg=MESSAGE_AUTHENTICATION,
        ): Maybe(jinja2_template),
        vol.Inclusive(
            CONFIG_PASSWORD,
            INCLUSION_GROUP_AUTHENTICATION,
            default=DEFAULT_PASSWORD,
            description=DESC_PASSWORD,
            msg=MESSAGE_AUTHENTICATION,
        ): Maybe(jinja2_template),
        vol.Optional(
            CONFIG_PAYLOAD,
            default=DEFAULT_PAYLOAD,
            description=DESC_PAYLOAD,
        ): Maybe(jinja2_template),
        vol.Optional(
            CONFIG_TIMEOUT,
            default=DEFAULT_TIMEOUT,
            description=DESC_TIMEOUT,
        ): vol.Coerce(int),
        vol.Optional(
            CONFIG_CONTENT_TYPE,
            default=DEFAULT_CONTENT_TYPE,
            description=DESC_CONTENT_TYPE,
        ): str,
        vol.Optional(
            CONFIG_VERIFY_SSL,
            default=DEFAULT_VERIFY_SSL,
            description=DESC_VERIFY_SSL,
        ): bool,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): {
            Slug(description=DESC_HOOK): HOOK_SCHEMA,
        },
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config: dict[str, Any]) -> bool:
    """Set up the webhook component."""
    Webhook(vis, config[COMPONENT])
    return True


class Webhook:
    """Initialize the webhook component."""

    def __init__(self, vis: Viseron, config: dict[str, Any]) -> None:
        self.vis = vis
        self.config = config
        self.jinja_env = Environment(loader=BaseLoader())
        self._setup_hooks()

    def _setup_hook(self, hook_name: str, hook_conf: dict[str, Any]) -> None:
        """Set up a single webhook."""

        def _handle_trigger(event_data: Event) -> None:
            """Handle the trigger event."""
            LOGGER.debug(
                f"Handling trigger for webhook '{hook_name}' "
                f"with event data: {event_data.as_json()}"
            )
            self._handle_event(hook_conf, event_data.data, hook_name)

        trigger = hook_conf[CONFIG_TRIGGER]
        event_type = trigger[CONFIG_EVENT]
        self.vis.listen_event(event_type, _handle_trigger)
        LOGGER.debug(f"Registered webhook '{hook_name}' for event '{event_type}'")

    def _setup_hooks(self):
        for hook_name, hook_conf in self.config.items():
            self._setup_hook(hook_name, hook_conf)

    def _handle_event(
        self, hook_conf: dict[str, Any], event: dict[str, Any], hook_name: str
    ):
        condition_template = hook_conf[CONFIG_TRIGGER][CONFIG_CONDITION]
        if condition_template:
            result, rendered_condition = render_template_condition(
                self.vis, self.jinja_env, condition_template, event=event
            )
            if not result:
                LOGGER.debug(
                    f"Webhook '{hook_name}' condition not met, skipping webhook. "
                    f"Condition: {rendered_condition}"
                )
                return

        url = render_template(
            self.vis, self.jinja_env, hook_conf[CONFIG_URL], event=event
        )
        if not url:
            LOGGER.error(f"Webhook '{hook_name}' URL is empty, skipping webhook")
            return

        payload = render_template(
            self.vis, self.jinja_env, hook_conf[CONFIG_PAYLOAD], event=event
        )
        headers = {}
        for header, value in hook_conf[CONFIG_HEADERS].items():
            rendered_value = render_template(
                self.vis, self.jinja_env, value, event=event
            )
            if rendered_value is not None:
                headers[str(header)] = str(rendered_value)

        auth = None
        if hook_conf[CONFIG_USERNAME] and hook_conf[CONFIG_PASSWORD]:
            auth = (hook_conf[CONFIG_USERNAME], hook_conf[CONFIG_PASSWORD])
        if hook_conf[CONFIG_CONTENT_TYPE]:
            headers["Content-Type"] = hook_conf[CONFIG_CONTENT_TYPE]

        try:
            LOGGER.debug(
                f"Sending webhook '{hook_name}' "
                f"with method: {hook_conf[CONFIG_METHOD].upper()}, "
                f"url: {url}, "
                f"headers: {headers}, "
                f"payload: {payload}"
            )
            resp = requests.request(
                method=hook_conf[CONFIG_METHOD],
                url=url,
                data=payload,
                headers=headers,
                timeout=hook_conf[CONFIG_TIMEOUT],
                verify=hook_conf[CONFIG_VERIFY_SSL],
                auth=auth,
            )
            LOGGER.debug(f"Webhook '{hook_name}' status code: {resp.status_code}")
        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error(f"Webhook '{hook_name}' error: {e}")
