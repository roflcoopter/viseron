"""Webhook component."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import requests

from viseron.helpers.template import render_template, render_template_condition

from .config import HookConfig, WebhookRoot
from .const import COMPONENT

if TYPE_CHECKING:
    from collections.abc import Callable

    from viseron import Viseron
    from viseron.events import Event

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = WebhookRoot


def setup(vis: Viseron, config: WebhookRoot) -> bool:
    """Set up the webhook component."""
    vis.data[COMPONENT] = Webhook(vis, config.webhook)
    return True


def unload(vis: Viseron) -> bool:
    """Unload the webhook component."""
    if COMPONENT in vis.data:
        vis.data[COMPONENT].unload()
        del vis.data[COMPONENT]
    return True


class Webhook:
    """Initialize the webhook component."""

    def __init__(self, vis: Viseron, config: dict[str, HookConfig]) -> None:
        self.vis = vis
        self.config = config
        self._event_listeners: list[Callable] = []
        self._setup_hooks()

    def _setup_hook(self, hook_name: str, hook_conf: HookConfig) -> None:
        """Set up a single webhook."""

        def _handle_trigger(event_data: Event) -> None:
            """Handle the trigger event."""
            LOGGER.debug(
                f"Handling trigger for webhook '{hook_name}' "
                f"with event data: {event_data.as_json()}"
            )
            self._handle_event(hook_conf, event_data.data, hook_name)

        event_type = hook_conf.trigger.event
        self._event_listeners.append(
            self.vis.listen_event(event_type, _handle_trigger),
        )
        LOGGER.debug(f"Registered webhook '{hook_name}' for event '{event_type}'")

    def _setup_hooks(self) -> None:
        for hook_name, hook_conf in self.config.items():
            self._setup_hook(hook_name, hook_conf)

    def _handle_event(
        self, hook_conf: HookConfig, event: dict[str, Any], hook_name: str
    ) -> None:
        condition_template = hook_conf.trigger.condition
        if condition_template:
            result, rendered_condition = render_template_condition(
                self.vis, condition_template, event=event
            )
            if not result:
                LOGGER.debug(
                    f"Webhook '{hook_name}' condition not met, skipping webhook. "
                    f"Condition: {rendered_condition}"
                )
                return

        url = render_template(self.vis, hook_conf.url, event=event)
        if not url:
            LOGGER.error(f"Webhook '{hook_name}' URL is empty, skipping webhook")
            return

        payload = render_template(self.vis, hook_conf.payload, event=event)
        headers = {}
        for header, value in hook_conf.headers.items():
            rendered_value = render_template(
                self.vis, value.get_secret_value(), event=event
            )
            if rendered_value is not None:
                headers[str(header)] = str(rendered_value)

        auth = None
        if hook_conf.username and hook_conf.password:
            auth = (hook_conf.username, hook_conf.password.get_secret_value())
        if hook_conf.content_type:
            headers["Content-Type"] = hook_conf.content_type

        # A custom CA certificate path takes precedence over the verify_ssl
        # boolean so that servers fronted by a self-hosted CA can be verified
        # without disabling TLS verification entirely.
        ca_cert = hook_conf.ca_cert
        verify = ca_cert or hook_conf.verify_ssl

        try:
            LOGGER.debug(
                f"Sending webhook '{hook_name}' "
                f"with method: {hook_conf.method.upper()}, "
                f"url: {url}, "
                f"headers: {list(headers)}, "
                f"payload: {payload}"
            )
            resp = requests.request(
                method=hook_conf.method,
                url=url,
                data=payload.encode("utf-8") if payload else None,
                headers=headers,
                timeout=hook_conf.timeout,
                verify=verify,
                auth=auth,
            )
            LOGGER.debug(f"Webhook '{hook_name}' status code: {resp.status_code}")
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(f"Error sending webhook '{hook_name}'")

    def unload(self) -> None:
        """Unload the webhook component."""
        for unsubscribe in self._event_listeners:
            unsubscribe()
        self._event_listeners.clear()
