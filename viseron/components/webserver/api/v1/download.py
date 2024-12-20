"""File download API Handler."""

import logging
import os
from asyncio import Lock
from http import HTTPStatus

import voluptuous as vol
from tornado import iostream
from tornado.web import StaticFileHandler

from viseron.components.webserver.api.handlers import BaseAPIHandler

LOGGER = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
}

DOWNLOAD_LOCK = Lock()


class DownloadAPIHandler(BaseAPIHandler):
    """Handler for API calls related to downloading files."""

    routes = [
        {
            "path_pattern": r"/download",
            "supported_methods": ["GET"],
            "method": "download",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Required("token"): str,
                },
            ),
        },
    ]

    async def download(self) -> None:
        """Download a file."""
        async with DOWNLOAD_LOCK:
            if self.request_arguments["token"] not in self._webserver.download_tokens:
                self.response_error(HTTPStatus.NOT_FOUND, reason="Token not found")
                return

            download_token = self._webserver.download_tokens.pop(
                self.request_arguments["token"]
            )

        if not os.path.exists(download_token.filename):
            self.response_error(HTTPStatus.NOT_FOUND, reason="File not found")
            return

        # Get file extension and check if allowed
        _, ext = os.path.splitext(download_token.filename)
        ext = ext.lower()

        if ext not in ALLOWED_EXTENSIONS:
            self.response_error(
                HTTPStatus.BAD_REQUEST, reason=f"Unsupported file type: {ext}"
            )
            return

        safe_filename = os.path.basename(download_token.filename)

        try:
            file_size = os.path.getsize(download_token.filename)

            self.set_header("Content-Type", ALLOWED_EXTENSIONS[ext])
            self.set_header("Content-Length", file_size)
            self.set_header(
                "Content-Disposition", f"attachment; filename={safe_filename}"
            )

            content = StaticFileHandler.get_content(download_token.filename, None, None)
            for chunk in content:
                try:
                    self.write(chunk)
                    await self.flush()
                except iostream.StreamClosedError:
                    return

        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error("Download failed: %s", str(e))
            self.response_error(
                HTTPStatus.INTERNAL_SERVER_ERROR, reason="Download failed"
            )
        finally:
            self.finish()
            os.remove(download_token.filename)
