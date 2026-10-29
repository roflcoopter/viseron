"""Static file handler that serves files by their persistent file key."""

from __future__ import annotations

import os
from http import HTTPStatus
from typing import TYPE_CHECKING

import tornado.web
from sqlalchemy import select

from viseron.components.storage.models import Files
from viseron.components.webserver.static_file_handler import (
    AccessTokenStaticFileHandler,
)

if TYPE_CHECKING:
    from viseron import Viseron

# Larger keys make PostgreSQL compare the BIGINT column as numeric, which cannot use
# the index and scans the whole table
MAX_FILE_KEY = 2**63 - 1


class FileKeyHandler(AccessTokenStaticFileHandler):
    """Serve a file by its file_key, which does not change when the file moves tier.

    Served at /file/<camera_identifier>/<hex file_key>. The camera is part of the
    URL so that access is validated before the database is queried.
    """

    # pylint: disable-next=arguments-differ
    def initialize(self, vis: Viseron) -> None:  # type: ignore[override]
        """Initialize the handler."""
        super().initialize("/", vis, camera_identifier="", failed=True)
        self._encoded_file_key = ""

    async def prepare(self) -> None:
        """Validate access to the camera in the URL."""
        self._camera_identifier, self._encoded_file_key = self.path_args[0].split("/")
        await super().prepare()

    def _resolve(self) -> str | None:
        """Return the path of the lowest tier that has the file on disk.

        Both the source and destination rows exist while a move is in flight. The
        source is preferred since the destination can still be mid-copy.
        """
        # Convert the hexadecimal file key from the URL to an integer.
        file_key = int(self._encoded_file_key, 16)
        if file_key > MAX_FILE_KEY:
            return None

        with self._get_session() as session:
            stmt = (
                select(Files.path)
                .where(Files.camera_identifier == self._camera_identifier)
                .where(Files.file_key == file_key)
                .order_by(Files.tier_id)
            )
            paths = session.execute(stmt).scalars().all()
        for path in paths:
            if os.path.exists(path):
                return path
        return None

    async def get(
        self,
        path: str,  # noqa: ARG002
        include_body: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        """Serve the file the key resolves to."""
        resolved_path = await self.run_in_executor(self._resolve)
        if resolved_path is None:
            raise tornado.web.HTTPError(HTTPStatus.NOT_FOUND)
        self.root = os.path.dirname(resolved_path)
        await super().get(os.path.basename(resolved_path), include_body)
