"""Static file handler that looks through tiers to find a potentially moved file."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from viseron.components.webserver.static_file_handler import (
    AccessTokenStaticFileHandler,
)

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


class TieredFileHandler(AccessTokenStaticFileHandler):
    """Static file handler that looks through tiers to find a potentially moved file."""

    # pylint: disable-next=arguments-differ
    def initialize(  # type: ignore[override]
        self,
        path: str,
        vis: Viseron,
        camera_identifier: str,
        failed: bool,
        category: str,
        subcategory: str,
        default_filename: str | None = None,
    ) -> None:
        """Initialize the handler."""
        super().initialize(path, vis, camera_identifier, failed, default_filename)
        self._category = category
        self._subcategory = subcategory
        self._tries = 0
        self._redirect = False

    def _search_file(self, path: str) -> str | None:
        """Search for a file in the tiers."""
        _path = os.path.join(self.root, path)
        LOGGER.debug("Searching for file %s", _path)
        with self._storage.camera_requested_files_count[self._camera_identifier](
            os.path.basename(_path)
        ):
            if os.path.exists(_path):
                LOGGER.debug("File %s exists, not searching tiers", _path)
                return None
            return self._storage.search_file(
                self._camera_identifier,
                self._category,
                self._subcategory,
                _path,
            )

    def compute_etag(self) -> str | None:
        """Compute the etag."""
        if self._redirect:
            return None
        return super().compute_etag()

    async def get(self, path, include_body=True) -> None:
        """Look through tiers to find a potentially moved file."""
        if not self._failed:
            while self._tries < 10:
                self._tries += 1
                redirect_path = await self.run_in_executor(self._search_file, path)
                if redirect_path:
                    LOGGER.debug("Redirecting to /files%s", redirect_path)
                    self._redirect = True
                    self.redirect(f"/files{redirect_path}", permanent=True)
                    return

                if not await self.run_in_executor(
                    os.path.exists, os.path.join(self.root, path)
                ):
                    await asyncio.sleep(0.1)
                    continue
                break
        await super().get(path, include_body)
