"""Tests for ViseronRequestHandler."""

from __future__ import annotations

import pytest

from viseron.components.webserver.request_handler import _redact_token_query


class TestRedactTokenQuery:
    """Tests for ``_redact_token_query``."""

    @pytest.mark.parametrize("value", [None, ""])
    def test_empty_returns_empty_string(self, value: str | None) -> None:
        """``None`` and empty strings yield an empty string."""
        assert _redact_token_query(value) == ""

    def test_no_query_returns_unchanged(self) -> None:
        """URI without a query string are returned unchanged."""
        uri = "/api/v1/cameras"
        assert _redact_token_query(uri) == uri

    def test_query_without_token_returns_unchanged(self) -> None:
        """Query strings without token params are returned unchanged."""
        uri = "/api/v1/cameras?foo=bar&baz=qux"
        assert _redact_token_query(uri) == uri

    def test_redacts_token_param(self) -> None:
        """``token=<value>`` is redacted."""
        assert (
            _redact_token_query("/stream?token=abc.def.ghi")
            == "/stream?token=<redacted>"
        )

    def test_redacts_access_token_param(self) -> None:
        """``access_token=<value>`` is redacted."""
        assert (
            _redact_token_query("/api/v1/x?access_token=abc.def.ghi")
            == "/api/v1/x?access_token=<redacted>"
        )

    def test_redacts_token_in_middle_of_query(self) -> None:
        """A token param after other params is redacted, others preserved."""
        assert (
            _redact_token_query("/x?foo=bar&token=secret&baz=qux")
            == "/x?foo=bar&token=<redacted>&baz=qux"
        )

    def test_redacts_token_at_end_of_query(self) -> None:
        """A token param at the end of the query is redacted."""
        assert (
            _redact_token_query("/x?foo=bar&access_token=secret")
            == "/x?foo=bar&access_token=<redacted>"
        )

    def test_redacts_multiple_token_params(self) -> None:
        """Both ``token`` and ``access_token`` are redacted in one URI."""
        result = _redact_token_query("/x?token=aaa&foo=bar&access_token=bbb")
        assert result == "/x?token=<redacted>&foo=bar&access_token=<redacted>"

    def test_case_insensitive(self) -> None:
        """Matching is case-insensitive on the parameter name."""
        assert (
            _redact_token_query("/x?Token=abc&Access_Token=def")
            == "/x?Token=<redacted>&Access_Token=<redacted>"
        )

    def test_does_not_redact_token_suffix_param(self) -> None:
        """Params like ``csrf_token`` or ``my_token`` are not redacted."""
        uri = "/x?csrf_token=abc&my_token=def"
        assert _redact_token_query(uri) == uri

    def test_preserves_fragment(self) -> None:
        """A fragment after the token value is preserved."""
        assert (
            _redact_token_query("/x?token=abc#section") == "/x?token=<redacted>#section"
        )

    def test_empty_token_value(self) -> None:
        """An empty token value is still redacted (no-op replacement)."""
        assert _redact_token_query("/x?token=&foo=bar") == "/x?token=<redacted>&foo=bar"
