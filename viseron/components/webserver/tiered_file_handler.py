"""Static file handler that looks through tiers to find a potentially moved file."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from viseron.components.storage.const import CONFIG_PATH
from viseron.components.webserver.const import MAX_FILE_SEARCH_TRIES
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

    @staticmethod
    def _path_contains(parent: str, child: str) -> bool:
        """Return if child is inside parent."""
        try:
            return os.path.commonpath([parent, child]) == parent
        except ValueError:
            return False

    def _configured_tier_paths(self) -> set[str]:
        """Return configured tier paths for this camera/category/subcategory."""
        return {
            os.path.normpath(tier_handler[self._subcategory].tier[CONFIG_PATH])
            for tier_handler in self._storage.camera_tier_handlers[
                self._camera_identifier
            ][self._category]
        }

    def handle_tier_hint(self, path: str) -> tuple[str, str] | None:
        """Handle tier hint arguments."""
        _path = os.path.normpath(os.path.join(self.root, path))
        first_tier_path = self.get_argument("first_tier_path", None, strip=True)
        actual_tier_path = self.get_argument("actual_tier_path", None, strip=True)

        if not first_tier_path or not actual_tier_path:
            return None

        first_tier_path = os.path.normpath(first_tier_path)
        actual_tier_path = os.path.normpath(actual_tier_path)
        configured_tier_paths = self._configured_tier_paths()
        if (
            first_tier_path not in configured_tier_paths
            or actual_tier_path not in configured_tier_paths
            or not self._path_contains(first_tier_path, _path)
        ):
            return None

        relative_path = os.path.relpath(_path, first_tier_path)
        hinted_path = os.path.normpath(os.path.join(actual_tier_path, relative_path))
        if not self._path_contains(actual_tier_path, hinted_path):
            return None

        LOGGER.debug(
            "first_tier_path and actual_tier_path found, adjusted path to %s",
            hinted_path,
        )
        if os.path.exists(hinted_path):
            return actual_tier_path, relative_path
        return None

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

    async def get(
        self,
        path: str,
        include_body: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        """Look through tiers to find a potentially moved file."""
        tier_hint_path = self.handle_tier_hint(path)
        if tier_hint_path:
            self.root, path = tier_hint_path
            await super().get(path, include_body)
            return

        if not self._failed:
            while self._tries < MAX_FILE_SEARCH_TRIES:
                self._tries += 1
                redirect_path = await self.run_in_executor(self._search_file, path)
                if redirect_path:
                    subpath = self.get_subpath()
                    LOGGER.debug("Redirecting to %s/files%s", subpath, redirect_path)
                    self._redirect = True
                    self.redirect(f"{subpath}/files{redirect_path}", permanent=True)
                    return

                if not await self.run_in_executor(
                    os.path.exists, os.path.join(self.root, path)
                ):
                    await asyncio.sleep(0.1)
                    continue
                break
        await super().get(path, include_body)
