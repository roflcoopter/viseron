"""Static file handler with authentication."""
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import tornado.web

from viseron.components.webserver.request_handler import ViseronRequestHandler

if TYPE_CHECKING:
    from viseron import Viseron


class AccessTokenStaticFileHandler(
    tornado.web.StaticFileHandler, ViseronRequestHandler
):
    """Static file handler."""

    def initialize(  # type: ignore # pylint: disable=arguments-differ
        self,
        path: str,
        vis: Viseron,
        camera_identifier,
        default_filename: str | None = None,
    ) -> None:
        """Initialize the handler."""
        tornado.web.StaticFileHandler.initialize(self, path, default_filename)
        ViseronRequestHandler.initialize(self, vis)  # type: ignore
        self._camera_identifier = camera_identifier

    async def prepare(self):
        """Validate access token."""
        if self._webserver.auth:
            if not self._camera_identifier:
                self.set_status(
                    HTTPStatus.BAD_REQUEST,
                    reason="Missing camera identifier in request",
                )
                self.finish()

            camera = self._get_camera(self._camera_identifier)
            if not camera:
                self.set_status(
                    HTTPStatus.NOT_FOUND,
                    reason=f"Camera {self._camera_identifier} not found",
                )
                self.finish()
                return

            if not await self.run_in_executor(self.validate_camera_token, camera):
                self.set_status(
                    HTTPStatus.UNAUTHORIZED,
                    reason="Unauthorized",
                )
                self.finish()
                return

        await super().prepare()
