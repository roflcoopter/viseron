"""Tests for the webhook component."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from viseron.components.webhook import CONFIG_PAYLOAD, HOOK_SCHEMA, Webhook

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
    "ca_cert": None,
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


CA_CERT_PATH = "/path/to/ca.pem"


class TestVerify:
    """Tests for how the webhook resolves the requests ``verify`` argument."""

    @staticmethod
    def _run(vis: MagicMock, hook_conf: dict) -> MagicMock:
        """Drive ``_handle_event`` and return the patched ``requests.request``."""
        mock_render = MagicMock()
        mock_render.side_effect = [VALID_URL, ASCII_PAYLOAD]

        with (
            patch("viseron.components.webhook.requests.request") as mock_request,
            patch("viseron.components.webhook.render_template", mock_render),
            patch(
                "viseron.components.webhook.render_template_condition",
                return_value=(True, "true"),
            ),
        ):
            webhook = Webhook(vis, {"test_hook": hook_conf})
            webhook._handle_event(hook_conf, {"name": "john"}, "test_hook")
        return mock_request

    def test_ca_cert_used_as_verify(self, vis: MagicMock) -> None:
        """A configured ca_cert path is passed as the verify argument."""
        hook_conf = dict(HOOK_CONFIG)
        hook_conf["ca_cert"] = CA_CERT_PATH

        mock_request = self._run(vis, hook_conf)

        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        assert kwargs["verify"] == CA_CERT_PATH

    def test_verify_ssl_true_when_no_ca_cert(self, vis: MagicMock) -> None:
        """Without ca_cert the boolean verify_ssl value is used unchanged."""
        hook_conf = dict(HOOK_CONFIG)
        hook_conf["ca_cert"] = None
        hook_conf["verify_ssl"] = True

        mock_request = self._run(vis, hook_conf)

        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        assert kwargs["verify"] is True

    def test_verify_ssl_false_when_no_ca_cert(self, vis: MagicMock) -> None:
        """verify_ssl: False is still honored when no ca_cert is set."""
        hook_conf = dict(HOOK_CONFIG)
        hook_conf["ca_cert"] = None
        hook_conf["verify_ssl"] = False

        mock_request = self._run(vis, hook_conf)

        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        assert kwargs["verify"] is False

    def test_ca_cert_takes_precedence_over_verify_ssl(self, vis: MagicMock) -> None:
        """ca_cert wins over verify_ssl when both are provided."""
        hook_conf = dict(HOOK_CONFIG)
        hook_conf["ca_cert"] = CA_CERT_PATH
        hook_conf["verify_ssl"] = False

        mock_request = self._run(vis, hook_conf)

        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        assert kwargs["verify"] == CA_CERT_PATH


class TestSchema:
    """Tests for HOOK_SCHEMA validation of the ca_cert option."""

    def test_ca_cert_accepts_string(self) -> None:
        """A string ca_cert validates and is preserved."""
        validated = HOOK_SCHEMA(
            {
                "trigger": {"event": "test_event"},
                "url": VALID_URL,
                "ca_cert": CA_CERT_PATH,
            }
        )
        assert validated["ca_cert"] == CA_CERT_PATH

    def test_ca_cert_defaults_to_none(self) -> None:
        """Omitting ca_cert defaults it to None."""
        validated = HOOK_SCHEMA(
            {
                "trigger": {"event": "test_event"},
                "url": VALID_URL,
            }
        )
        assert validated["ca_cert"] is None
