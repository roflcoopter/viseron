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


def _is_same_or_child(path: str, root: str) -> bool:
    """Return True if path is root or a file under root."""
    path_n = os.path.normpath(path)
    root_n = os.path.normpath(root)
    return path_n == root_n or path_n.startswith(root_n + os.sep)


def rewrite_tier_hint_path(
    original_path: str,
    first_tier_path: str,
    actual_tier_path: str,
    allowed_tier_paths: list[str],
) -> str | None:
    """Rewrite a first-tier path to the actual tier, if both are allowlisted.

    Query parameters on /files are attacker-controlled. Without this check a
    request can replace the storage prefix with an arbitrary directory
    (for example /etc) and redirect into it.
    """
    first = os.path.normpath(first_tier_path)
    actual = os.path.normpath(actual_tier_path)
    allowed = {os.path.normpath(path) for path in allowed_tier_paths}
    if first not in allowed or actual not in allowed:
        LOGGER.debug(
            "Ignoring tier hint with unconfigured paths first=%s actual=%s",
            first,
            actual,
        )
        return None

    original = os.path.normpath(original_path)
    if not _is_same_or_child(original, first):
        return None

    rewritten = os.path.normpath(actual + original[len(first) :])
    if not _is_same_or_child(rewritten, actual):
        return None
    return rewritten


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

    def _configured_tier_paths(self) -> list[str]:
        """Return configured storage tier paths for this camera."""
        paths: list[str] = []
        camera_handlers = self._storage.camera_tier_handlers.get(
            self._camera_identifier, {}
        )
        for category in camera_handlers.values():
            for tier in category:
                for handler in tier.values():
                    tier_path = handler.tier.get(CONFIG_PATH)
                    if tier_path:
                        paths.append(tier_path)
        return paths

    def handle_tier_hint(self, path: str) -> str | None:
        """Handle tier hint arguments."""
        first_tier_path = self.get_argument("first_tier_path", None, strip=True)
        actual_tier_path = self.get_argument("actual_tier_path", None, strip=True)
        if not first_tier_path or not actual_tier_path:
            return None

        rewritten = rewrite_tier_hint_path(
            os.path.join(self.root, path),
            first_tier_path,
            actual_tier_path,
            self._configured_tier_paths(),
        )
        if rewritten:
            LOGGER.debug(
                "first_tier_path and actual_tier_path found, adjusted path to %s",
                rewritten,
            )
        return rewritten

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
        tier_hint_redirect_path = self.handle_tier_hint(path)
        if tier_hint_redirect_path:
            subpath = self.get_subpath()
            self._redirect = True
            self.redirect(f"{subpath}/files{tier_hint_redirect_path}", permanent=True)
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
