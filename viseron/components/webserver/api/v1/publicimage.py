"""Public image API Handler."""

import logging
import os
from http import HTTPStatus

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.const import PUBLIC_IMAGES_PATH
from viseron.helpers import utcnow

LOGGER = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


class PublicimageAPIHandler(BaseAPIHandler):
    """Handler for API calls related to public image access."""

    routes = [
        {
            "path_pattern": r"/publicimage",
            "supported_methods": ["GET"],
            "method": "get_public_image",
            "requires_auth": False,
            "request_arguments_schema": vol.Schema(
                {
                    vol.Required("token"): str,
                },
            ),
        },
    ]

    async def get_public_image(self) -> None:
        """Get a public image using a token."""
        token = self.request_arguments["token"]

        # Try to get token from memory first
        public_image_token = self._webserver.public_image_tokens.get(token)

        # If token not in memory, try to find file on disk (survives restart)
        if not public_image_token:
            # Construct expected file path
            file_path = os.path.join(PUBLIC_IMAGES_PATH, f"{token}.jpg")

            # Check if file exists on disk
            if not await self.run_in_executor(os.path.exists, file_path):
                LOGGER.debug(f"Token not found in memory and file not on disk: {token}")
                self.response_error(HTTPStatus.NOT_FOUND, reason="Token not found")
                return

            # File exists but token not in memory - happens after restart
            # We can't validate download limits, but we serve the file anyway
            # The cleanup task will eventually remove expired files
            LOGGER.debug(
                f"Token {token} not in memory but file exists on disk, serving anyway"
            )
        else:
            # Token is in memory, check if expired
            now = await self.run_in_executor(utcnow)
            if public_image_token.expires_at < now:
                LOGGER.debug(f"Token expired: {token}")
                # Clean up expired token and file
                file_path = public_image_token.file_path
                if await self.run_in_executor(os.path.exists, file_path):
                    await self.run_in_executor(os.remove, file_path)
                del self._webserver.public_image_tokens[token]
                self.response_error(HTTPStatus.UNAUTHORIZED, reason="Token expired")
                return

            file_path = public_image_token.file_path

            # Check if file exists
            if not await self.run_in_executor(os.path.exists, file_path):
                LOGGER.debug(f"File not found: {file_path}")
                # Clean up invalid token
                del self._webserver.public_image_tokens[token]
                self.response_error(HTTPStatus.NOT_FOUND, reason="File not found")
                return

        # Get file extension and check if allowed
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext not in ALLOWED_EXTENSIONS:
            LOGGER.warning(f"Unsupported file type: {ext}")
            self.response_error(
                HTTPStatus.BAD_REQUEST, reason=f"Unsupported file type: {ext}"
            )
            return

        try:
            # Read the image file
            def read_image():
                with open(file_path, "rb") as f:
                    return f.read()

            image_data = await self.run_in_executor(read_image)

            # Decrement remaining downloads counter if token is in memory
            should_delete_after_serving = False
            if public_image_token and public_image_token.remaining_downloads > 0:
                public_image_token.remaining_downloads -= 1
                LOGGER.debug(
                    f"Token {token} remaining downloads: "
                    f"{public_image_token.remaining_downloads}"
                )

                # Check if this was the last allowed download
                if public_image_token.remaining_downloads <= 0:
                    should_delete_after_serving = True
                    LOGGER.debug(
                        f"Token {token} reached final download, "
                        "will clean up after serving"
                    )

            # Set appropriate headers
            self.set_header("Content-Type", ALLOWED_EXTENSIONS[ext])
            self.set_header("Cache-Control", "public, max-age=3600")
            self.set_header("Content-Length", len(image_data))

            # Write the image data and finish
            self.write(image_data)
            await self.finish()

            # Clean up after serving if this was the last download
            if should_delete_after_serving:
                LOGGER.debug(f"Cleaning up token {token} after final download")
                if await self.run_in_executor(os.path.exists, file_path):
                    await self.run_in_executor(os.remove, file_path)
                del self._webserver.public_image_tokens[token]

        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error(f"Failed to serve public image: {str(e)}")
            self.response_error(
                HTTPStatus.INTERNAL_SERVER_ERROR, reason="Failed to serve image"
            )
