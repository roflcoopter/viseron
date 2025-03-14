"""Common mocks for Viseron webserver tests."""
from __future__ import annotations

import json
import logging
import os
from typing import Any
from unittest.mock import patch

import pytest
from tornado.httpclient import HTTPResponse
from tornado.testing import AsyncHTTPTestCase
from tornado.web import create_signed_value

from viseron import setup_viseron
from viseron.components.webserver import Webserver, create_application
from viseron.components.webserver.const import COMPONENT

USER_ID = "ffa448c2623b45ba8be62bfc6b0ae859"
USER_NAME = "asd"

REFRESH_TOKEN_ID = "77541fd8343543a7be6057270b23cdfe"
CLIENT_ID = "http://dummy.lan:8888/"

STATIC_ASSET_KEY = "static_asset_key"

AUTH_STORAGE_DATA = {
    "version": 1,
    "data": {
        "users": {
            USER_ID: {
                "name": "Asd",
                "username": USER_NAME,
                "password": "JDJiJDEyJFJsNm9HeVVKcEx5cXlXSlFsaFBVNWVhVlJ3TWJaRlR4d3U4YUo0Y2JwaC4uU0VMbjliWlUy",  # pylint: disable=line-too-long
                "group": "admin",
                "id": USER_ID,
                "enabled": True,
            }
        },
        "refresh_tokens": {
            REFRESH_TOKEN_ID: {
                "user_id": USER_ID,
                "client_id": CLIENT_ID,
                "session_expiration": 3600,
                "access_token_type": "normal",
                "access_token_expiration": 1800,
                "created_at": 1678198479.662633,
                "id": REFRESH_TOKEN_ID,
                "token": "token",
                "jwt_key": "jwt_key",
                "static_asset_key": STATIC_ASSET_KEY,
                "used_at": 1678196574.598274,
                "used_by": "192.168.100.100",
            },
        },
    },
}


class TestAppBase(AsyncHTTPTestCase):
    """Base class for testing the API."""

    config: dict[str, Any] = {}

    @pytest.fixture(autouse=True)
    def inject_caplog(self, caplog):
        """Inject caplog fixture."""
        self._caplog = caplog  # pylint: disable=attribute-defined-outside-init
        self._caplog.set_level(logging.DEBUG)

    def setUp(self) -> None:
        """Set up the test."""
        # Mock the real application so we dont listen on the same port twice
        with patch("viseron.load_config") as mocked_load_config, patch(
            "viseron.components.webserver.create_application"
        ):
            mocked_load_config.return_value = self.config
            self.vis = setup_viseron(start_background_scheduler=False)
        self.webserver: Webserver = self.vis.data[COMPONENT]
        return super().setUp()

    def tearDown(self) -> None:
        """Tear down the test."""
        super().tearDown()
        self.vis.shutdown()

    def get_app(self):
        """Get the application.

        Required override for AsyncHTTPTestCase.
        AsyncHTTPTestCase does not support xsrf_cookies, so we disable it here.
        """
        app = create_application(
            self.vis, {"debug": False}, "dummy_secret", xsrf_cookies=False
        )
        return app


class TestAppBaseNoAuth(TestAppBase):
    """Base class for testing the API without auth."""

    config = {"webserver": None}


class TestAppBaseAuth(TestAppBase):
    """Base class for testing the API with auth."""

    config = {"webserver": {"auth": None}}

    def tearDown(self) -> None:
        """Tear down the test."""
        if os.path.exists(
            self.webserver.auth._auth_store.path  # pylint: disable=protected-access
        ):
            os.remove(
                self.webserver.auth._auth_store.path  # pylint: disable=protected-access
            )
        if os.path.exists(self.webserver.auth.onboarding_path()):
            os.remove(self.webserver.auth.onboarding_path())
        return super().tearDown()

    def fetch_with_auth(
        self,
        path: str,
        raise_error: bool = False,
        token_parameter: bool = False,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Add authentication headers when running fetch."""
        os.makedirs(
            os.path.dirname(
                self.webserver.auth._auth_store.path  # pylint: disable=protected-access
            ),
            exist_ok=True,
        )
        with open(
            self.webserver.auth._auth_store.path,  # pylint: disable=protected-access
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(AUTH_STORAGE_DATA, file)

        if "headers" not in kwargs:
            kwargs["headers"] = {}

        # Add refresh token cookie
        refresh_token = self.webserver.auth.get_refresh_token(REFRESH_TOKEN_ID)
        refresh_token_cookie = create_signed_value(
            self._app.settings["cookie_secret"],
            "refresh_token",
            "token",
        ).decode()
        kwargs["headers"][
            "Cookie"
        ] = f"refresh_token={refresh_token_cookie};user={USER_ID};"

        # Create access token
        access_token = self.webserver.auth.generate_access_token(
            refresh_token, "dummy.lan"
        )
        header, payload, signature = access_token.split(".")

        # Add optional static asset key cookie
        static_asset_key_cookie = create_signed_value(
            self._app.settings["cookie_secret"],
            "static_asset_key",
            kwargs.pop("static_asset_key_cookie", STATIC_ASSET_KEY),
        ).decode()
        kwargs["headers"]["Cookie"] += f"static_asset_key={static_asset_key_cookie};"

        if token_parameter:
            if "?" in path:
                path += "&"
            else:
                path += "?"
            path += f"token={header}.{payload}"
            signature_token_cookie = create_signed_value(
                self._app.settings["cookie_secret"],
                "signature_cookie",
                signature,
            ).decode()
            kwargs["headers"]["Cookie"] += f"signature_cookie={signature_token_cookie};"
        else:
            if not kwargs["headers"].get("Authorization", False):
                kwargs["headers"]["Authorization"] = "Bearer " + access_token

        return self.fetch(path, raise_error, **kwargs)
