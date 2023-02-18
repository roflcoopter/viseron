"""Viseron request handler."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import tornado.web
from tornado.ioloop import IOLoop

from viseron.components.webserver.const import COMPONENT

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.webserver import Webserver
    from viseron.components.webserver.auth import RefreshToken, User

LOGGER = logging.getLogger(__name__)


class ViseronRequestHandler(tornado.web.RequestHandler):
    """Base request handler."""

    def initialize(self, vis: Viseron):
        """Initialize request handler."""
        self._vis = vis
        self._webserver: Webserver = vis.data[COMPONENT]
        # Manually set xsrf cookie
        self.xsrf_token  # pylint: disable=pointless-statement

    async def run_in_executor(self, func, *args):
        """Run function in executor."""
        return await IOLoop.current().run_in_executor(None, func, *args)

    async def prepare(self):  # pylint: disable=invalid-overridden-method
        """Prepare request handler.

        get_current_user cannot be async, so we set self.current_user here.
        """
        if not self._webserver.auth:
            return

        _user = self.get_cookie("user")
        if _user:
            self.current_user = await self.run_in_executor(
                self._webserver.auth.get_user, _user
            )

    def set_cookies(
        self,
        refresh_token: RefreshToken,
        access_token: str,
        user: User,
        new_session=False,
    ):
        """Set session cookies."""
        now = datetime.utcnow()

        _header, _payload, signature = access_token.split(".")

        expires = (
            now + self._webserver.auth.session_expiry
            if self._webserver.auth.session_expiry
            else now + timedelta(days=3650)
        )
        # Refresh all cookies on every request if expiry is None because you can't have
        # infinite cookies in some browsers
        if new_session or self._webserver.auth.session_expiry is None:
            self.clear_cookie("refresh_token")
            self.set_secure_cookie(  # Not a JWT
                "refresh_token",
                refresh_token.token,
                expires=expires,
                httponly=True,
                samesite="strict",
                secure=bool(self.request.protocol == "https"),
            )
            self.clear_cookie("user")
            self.set_cookie(
                "user",
                user.id,
                expires=expires,
                samesite="strict",
                secure=bool(self.request.protocol == "https"),
            )
        self.clear_cookie("signature_cookie")
        self.set_secure_cookie(
            "signature_cookie",
            signature,
            expires=expires,
            httponly=True,
            samesite="strict",
            secure=bool(self.request.protocol == "https"),
        )

    def validate_access_token(
        self, access_token: str, check_refresh_token: bool = True
    ):
        """Validate access token."""
        # Check access token is valid
        refresh_token = self._webserver.auth.validate_access_token(access_token)
        if refresh_token is None:
            LOGGER.debug("Access token not valid")
            return False

        # Check refresh_token cookie exists
        if check_refresh_token:
            refresh_token_cookie = self.get_secure_cookie("refresh_token")
            if refresh_token_cookie is None:
                LOGGER.debug("Refresh token is missing")
                return
            if refresh_token_cookie.decode() != refresh_token.token:
                LOGGER.debug("Access token does not belong to the refresh token.")
                return False

        user = self._webserver.auth.get_user(refresh_token.user_id)
        if user is None or not user.enabled:
            LOGGER.debug("User not found or disabled")
            return False

        if self.current_user != user:
            LOGGER.debug("User mismatch")
            return False

        return True
