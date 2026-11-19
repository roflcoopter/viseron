"""Tests for ViseronRequestHandler."""

from unittest.mock import MagicMock, patch

import pytest
from tornado.httputil import HTTPHeaders

from viseron.components.webserver.request_handler import ViseronRequestHandler


@pytest.fixture
def handler():
    """Create a ViseronRequestHandler with mocked internals."""
    with patch.object(
        ViseronRequestHandler,
        "__init__",
        MagicMock(spec=ViseronRequestHandler, return_value=None),
    ):
        _handler = ViseronRequestHandler.__new__(ViseronRequestHandler)
        _handler.request = MagicMock()
        _handler._webserver = MagicMock()
        yield _handler


class TestGetSubpath:
    """Tests for get_subpath."""

    def test_returns_ingress_path_when_header_set(
        self, handler: ViseronRequestHandler
    ) -> None:
        """Ingress header should be returned, normalized."""
        handler.request.headers = HTTPHeaders(
            {"X-Ingress-Path": "/api/hassio_ingress/abc123"}
        )
        handler._webserver.configured_subpath = "/configured"

        result = handler.get_subpath()

        assert result == "/api/hassio_ingress/abc123"

    def test_normalizes_ingress_path_trailing_slash(
        self, handler: ViseronRequestHandler
    ) -> None:
        """Trailing slash on ingress path should be stripped."""
        handler.request.headers = HTTPHeaders({"X-Ingress-Path": "/ingress/path/"})
        handler._webserver.configured_subpath = "/configured"

        result = handler.get_subpath()

        assert result == "/ingress/path"

    def test_normalizes_ingress_path_no_leading_slash(
        self, handler: ViseronRequestHandler
    ) -> None:
        """Ingress path without leading slash gets one added."""
        handler.request.headers = HTTPHeaders({"X-Ingress-Path": "ingress/path"})
        handler._webserver.configured_subpath = "/configured"

        result = handler.get_subpath()

        assert result == "/ingress/path"

    def test_falls_back_to_configured_subpath(
        self, handler: ViseronRequestHandler
    ) -> None:
        """Missing ingress header should fall back to configured_subpath."""
        handler.request.headers = HTTPHeaders()
        handler._webserver.configured_subpath = "/my-subpath"

        result = handler.get_subpath()

        assert result == "/my-subpath"

    def test_returns_empty_string_when_no_ingress_and_no_subpath(
        self, handler: ViseronRequestHandler
    ) -> None:
        """No ingress header and empty configured subpath returns empty string."""
        handler.request.headers = HTTPHeaders()
        handler._webserver.configured_subpath = ""

        result = handler.get_subpath()

        assert result == ""

    def test_ignores_empty_ingress_header(self, handler: ViseronRequestHandler) -> None:
        """Empty X-Ingress-Path header should fall back to configured_subpath."""
        handler.request.headers = HTTPHeaders({"X-Ingress-Path": ""})
        handler._webserver.configured_subpath = "/fallback"

        result = handler.get_subpath()

        assert result == "/fallback"

    def test_ingress_path_takes_precedence_over_configured(
        self, handler: ViseronRequestHandler
    ) -> None:
        """Ingress path should always win over configured_subpath."""
        handler.request.headers = HTTPHeaders({"X-Ingress-Path": "/ingress"})
        handler._webserver.configured_subpath = "/configured"

        result = handler.get_subpath()

        assert result == "/ingress"


class TestClearAllCookies:
    """Tests for clear_all_cookies."""

    def test_forwards_kwargs_as_keywords(self, handler: ViseronRequestHandler) -> None:
        """Keyword arguments must be forwarded as keywords to clear_cookie.

        The cookie attributes (path, domain, ...) are required to clear a
        cookie that was set with them. Splashing the kwargs dict with *
        passes the dict keys as positional arguments instead.
        """
        handler.request.cookies = {"session": "value", "_xsrf": "token"}
        handler.clear_cookie = MagicMock()

        handler.clear_all_cookies(path="/", httponly=True)

        handler.clear_cookie.assert_any_call("session", path="/", httponly=True)

    def test_keeps_xsrf_cookie(self, handler: ViseronRequestHandler) -> None:
        """The XSRF cookie must survive a clear-all."""
        handler.request.cookies = {"session": "value", "_xsrf": "token"}
        handler.clear_cookie = MagicMock()

        handler.clear_all_cookies()

        for cookie_call in handler.clear_cookie.mock_calls:
            assert "_xsrf" not in str(cookie_call)
