"""Viseron request handler."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import tornado.web
from tornado.ioloop import IOLoop

from viseron.components.webserver.const import COMPONENT

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.webserver import Webserver
    from viseron.components.webserver.auth import RefreshToken, User


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

        if new_session:
            self.clear_cookie("refresh_token")
            self.set_secure_cookie(  # Not a JWT
                "refresh_token",
                refresh_token.token,
                expires=now + self._webserver.auth.session_expiry,
                httponly=True,
                samesite="strict",
                secure=bool(self.request.protocol == "https"),
            )
            self.clear_cookie("user")
            self.set_cookie(
                "user",
                user.id,
                expires=now + self._webserver.auth.session_expiry,
                samesite="strict",
                secure=bool(self.request.protocol == "https"),
            )
        self.clear_cookie("signature_cookie")
        self.set_secure_cookie(
            "signature_cookie",
            signature,
            expires=now + self._webserver.auth.session_expiry,
            httponly=True,
            samesite="strict",
            secure=bool(self.request.protocol == "https"),
        )
