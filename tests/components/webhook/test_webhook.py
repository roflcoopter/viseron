"""Tests for the webhook component."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, call, patch

import pytest

from viseron.components.webhook import CONFIG_SCHEMA, setup, unload
from viseron.components.webhook.const import COMPONENT
from viseron.events import Event
from viseron.helpers.config_validation import validate_config

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tests.conftest import MockViseron

    Trigger = Callable[..., MagicMock]

EVENT = "camera_one/motion_detected"
URL = "http://localhost/test"
CA_CERT_PATH = "/path/to/ca.pem"


def make_config(**keys: Any) -> dict[str, Any]:
    """Return a config with one hook, test_hook, that has the given keys."""
    return {COMPONENT: {"test_hook": {"trigger": {"event": EVENT}, "url": URL, **keys}}}


@pytest.fixture(name="request_mock")
def fixture_request_mock() -> Iterator[MagicMock]:
    """Patch the HTTP request sent by the webhook."""
    with patch("viseron.components.webhook.requests.request") as request:
        yield request


@pytest.fixture(name="trigger")
def fixture_trigger(vis: MockViseron, request_mock: MagicMock) -> Trigger:
    """Return a function that sets up the webhook and fires its event.

    It returns the patched requests.request.
    """

    def _trigger(event_data: dict[str, Any] | None = None, **keys: Any) -> MagicMock:
        setup(vis, validate_config(CONFIG_SCHEMA, make_config(**keys)))
        handler = vis.listen_event.call_args.args[1]
        handler(Event(EVENT, event_data or {}, 0.0))
        return request_mock

    return _trigger


def request_kwargs(request_mock: MagicMock) -> dict[str, Any]:
    """Return the keyword arguments of the only request that was sent."""
    request_mock.assert_called_once()
    return request_mock.call_args.kwargs


def test_listens_to_the_event_of_each_hook(vis: MockViseron) -> None:
    """Each hook listens to its own trigger event, and unload stops listening."""
    config = make_config()
    config[COMPONENT]["other_hook"] = {"trigger": {"event": "other"}, "url": URL}
    setup(vis, validate_config(CONFIG_SCHEMA, config))

    assert [listen.args[0] for listen in vis.listen_event.call_args_list] == [
        EVENT,
        "other",
    ]
    unload(vis)
    assert vis.listen_event.return_value.call_args_list == [call(), call()]
    assert COMPONENT not in vis.data


def test_defaults(trigger: Trigger) -> None:
    """A minimal hook sends a GET request with the default options."""
    assert request_kwargs(trigger()) == {
        "method": "get",
        "url": URL,
        "data": None,
        "headers": {"Content-Type": "application/json"},
        "timeout": 10,
        "verify": True,
        "auth": None,
    }


def test_every_option(trigger: Trigger) -> None:
    """Every option of a hook reaches the request, templates rendered."""
    kwargs = request_kwargs(
        trigger(
            {"camera_identifier": "camera_one", "token": "abc"},
            url="http://localhost/{{ event.camera_identifier }}",
            method="PUT",
            headers={
                "Authorization": "Bearer {{ event.token }}",
                "X-Static": "static",
            },
            username="user",
            password="pass",
            payload='{"camera": "{{ event.camera_identifier }}"}',
            timeout=5,
            content_type="text/plain",
            verify_ssl=False,
        )
    )
    assert kwargs == {
        "method": "put",
        "url": "http://localhost/camera_one",
        "data": b'{"camera": "camera_one"}',
        "headers": {
            "Authorization": "Bearer abc",
            "X-Static": "static",
            "Content-Type": "text/plain",
        },
        "timeout": 5,
        "verify": False,
        "auth": ("user", "pass"),
    }


@pytest.mark.parametrize(
    ("condition", "sent"),
    [
        ("{{ event.motion_detected }}", True),
        ("{{ not event.motion_detected }}", False),
    ],
)
def test_condition(trigger: Trigger, condition: str, sent: bool) -> None:
    """The request is only sent if the condition renders to a truthy value."""
    request_mock = trigger(
        {"motion_detected": True},
        trigger={"event": EVENT, "condition": condition},
    )
    assert request_mock.called is sent


@pytest.mark.parametrize("url", ["{{ event.url }}", None])
def test_empty_url_is_skipped(trigger: Trigger, url: str | None) -> None:
    """No request is sent if the URL renders to an empty string or is null."""
    assert not trigger({"url": ""}, url=url).called


def test_empty_content_type_sends_no_header(trigger: Trigger) -> None:
    """An empty content_type leaves the Content-Type header out."""
    assert request_kwargs(trigger(content_type=""))["headers"] == {}


def test_header_rendered_empty_is_left_out(trigger: Trigger) -> None:
    """A header whose value renders to nothing is not sent."""
    kwargs = request_kwargs(trigger(headers={"X-Empty": ""}))
    assert kwargs["headers"] == {"Content-Type": "application/json"}


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param('{"name": "ř"}', id="utf8"),
        pytest.param('{"name": "john"}', id="ascii"),
    ],
)
def test_payload_encoded_as_utf8(trigger: Trigger, payload: str) -> None:
    """The payload is sent as UTF-8 bytes.

    The requests library defaults to latin-1 encoding when data is a str
    without an explicit charset in Content-Type. Payloads containing
    non-ASCII characters like 'ř' (U+0159) must be pre-encoded to UTF-8
    bytes to avoid UnicodeEncodeError.
    """
    assert request_kwargs(trigger(payload=payload))["data"] == payload.encode("utf-8")


@pytest.mark.parametrize(
    ("keys", "verify"),
    [
        pytest.param({"ca_cert": CA_CERT_PATH}, CA_CERT_PATH, id="ca_cert"),
        pytest.param({"verify_ssl": True}, True, id="verify_ssl_true"),
        pytest.param({"verify_ssl": False}, False, id="verify_ssl_false"),
        pytest.param(
            {"ca_cert": CA_CERT_PATH, "verify_ssl": False},
            CA_CERT_PATH,
            id="ca_cert_over_verify_ssl",
        ),
    ],
)
def test_verify(trigger: Trigger, keys: dict[str, Any], verify: str | bool) -> None:
    """A ca_cert path takes precedence over verify_ssl."""
    assert request_kwargs(trigger(**keys))["verify"] == verify


def test_header_values_are_not_logged(
    trigger: Trigger, caplog: pytest.LogCaptureFixture
) -> None:
    """Header values can be secrets, so only the header names are logged."""
    caplog.set_level(logging.DEBUG, logger="viseron.components.webhook")
    trigger(headers={"Authorization": "Bearer secret_token"})
    assert "Authorization" in caplog.text
    assert "secret_token" not in caplog.text


def test_request_error_is_logged(
    trigger: Trigger, request_mock: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """An error while sending the request is logged, not raised."""
    request_mock.side_effect = OSError("boom")
    trigger()
    assert "Error sending webhook 'test_hook'" in caplog.text
