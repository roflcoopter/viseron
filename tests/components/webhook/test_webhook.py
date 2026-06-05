"""Tests for the webhook component."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from viseron.components.webhook import CONFIG_PAYLOAD, Webhook

HOOK_CONFIG: dict = {
    "trigger": {"event": "test_event", "condition": None},
    "url": "http://localhost/test",
    "method": "post",
    "headers": {},
    "username": None,
    "password": None,
    "payload": '{"name": "{{ name }}"}',
    "timeout": 10,
    "content_type": "application/json",
    "verify_ssl": True,
}

VALID_URL = "http://localhost/test"
UTF8_PAYLOAD = '{"name": "\u0159"}'
ASCII_PAYLOAD = '{"name": "john"}'


@pytest.fixture(name="vis")
def fixture_vis():
    """Create a mock Viseron instance."""
    vis = MagicMock()
    vis.data = {}
    vis.listen_event = MagicMock()
    vis.jinja_env = MagicMock()
    vis.states = MagicMock()
    return vis


class TestPayloadEncoding:
    """Tests for webhook payload encoding behavior."""

    @patch("viseron.components.webhook.requests.request")
    def test_utf8_chars_encoded_as_bytes(
        self, mock_request: MagicMock, vis: MagicMock
    ) -> None:
        """Test that payloads with UTF-8 characters are encoded as bytes.

        The requests library defaults to latin-1 encoding when data is a str
        without an explicit charset in Content-Type. Payloads containing
        non-ASCII characters like 'ř' (U+0159) must be pre-encoded to UTF-8
        bytes to avoid UnicodeEncodeError.
        """
        mock_render = MagicMock()
        mock_render.side_effect = [VALID_URL, UTF8_PAYLOAD]

        with (
            patch("viseron.components.webhook.render_template", mock_render),
            patch(
                "viseron.components.webhook.render_template_condition",
                return_value=(True, "true"),
            ),
        ):
            webhook = Webhook(vis, {"test_hook": HOOK_CONFIG})
            webhook._handle_event(HOOK_CONFIG, {"name": "ř"}, "test_hook")

        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        data_arg = kwargs["data"]

        assert isinstance(data_arg, bytes), (
            f"Expected data to be bytes, got {type(data_arg)}: {data_arg!r}"
        )
        assert data_arg == UTF8_PAYLOAD.encode("utf-8"), (
            f"Expected UTF-8 encoded bytes, got {data_arg!r}"
        )

    @patch("viseron.components.webhook.requests.request")
    def test_ascii_payload_still_works(
        self, mock_request: MagicMock, vis: MagicMock
    ) -> None:
        """Test that ASCII-only payloads are still encoded correctly."""
        mock_render = MagicMock()
        mock_render.side_effect = [VALID_URL, ASCII_PAYLOAD]

        with (
            patch("viseron.components.webhook.render_template", mock_render),
            patch(
                "viseron.components.webhook.render_template_condition",
                return_value=(True, "true"),
            ),
        ):
            webhook = Webhook(vis, {"test_hook": HOOK_CONFIG})
            webhook._handle_event(HOOK_CONFIG, {"name": "john"}, "test_hook")

        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        data_arg = kwargs["data"]

        assert isinstance(data_arg, bytes), (
            f"Expected data to be bytes, got {type(data_arg)}: {data_arg!r}"
        )
        assert data_arg == ASCII_PAYLOAD.encode("utf-8")

    @patch("viseron.components.webhook.requests.request")
    def test_none_payload_not_encoded(
        self, mock_request: MagicMock, vis: MagicMock
    ) -> None:
        """Test that None payload is passed as None, not encoded."""
        mock_render = MagicMock()
        mock_render.side_effect = [VALID_URL, None]

        hook_config_no_payload = dict(HOOK_CONFIG)
        hook_config_no_payload[CONFIG_PAYLOAD] = None

        with (
            patch("viseron.components.webhook.render_template", mock_render),
            patch(
                "viseron.components.webhook.render_template_condition",
                return_value=(True, "true"),
            ),
        ):
            webhook = Webhook(vis, {"test_hook": hook_config_no_payload})
            webhook._handle_event(hook_config_no_payload, {}, "test_hook")

        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        assert kwargs["data"] is None
