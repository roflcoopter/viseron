"""Viseron request handler."""
from __future__ import annotations

from typing import TYPE_CHECKING

import tornado.web
from tornado.ioloop import IOLoop

from viseron.components.webserver.const import COMPONENT

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.webserver import Webserver


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
        _user = self.get_secure_cookie("user")
        if _user:
            self.current_user = await self.run_in_executor(
                self._webserver.auth.get_user, _user.decode()
            )
