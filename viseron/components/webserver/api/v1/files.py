"""API handler for serving storage files by logical id."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
from email.utils import formatdate
from functools import partial
from http import HTTPStatus

from viseron.components.storage.const import (
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
)
from viseron.components.storage.files import (
    ResolvedFile,
    resolve_file_id,
)
from viseron.components.webserver.api.handlers import BaseAPIHandler

LOGGER = logging.getLogger(__name__)
__all__ = [
    "HLS_SEGMENT_FILE_TYPES",
    "ResolvedFile",
    "authorize_file_request",
    "resolve_file_id",
    "serve_resolved_file",
]
HLS_SEGMENT_FILE_TYPES = frozenset(
    {
        (TIER_CATEGORY_RECORDER, TIER_SUBCATEGORY_SEGMENTS),
    }
)

CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".mp4": "video/mp4",
    ".m4s": "video/iso.segment",
}
CHUNK_SIZE = 1024 * 1024


class FileRangeError(ValueError):
    """Raised when a Range header cannot be satisfied."""


async def authorize_file_request(
    handler: BaseAPIHandler,
    camera_identifier: str,
    *,
    failed: bool = False,
) -> bool:
    """Authorize a file request against the file's camera."""
    if not handler.webserver.auth:
        return True

    if await handler.run_in_executor(handler.validate_auth_header):
        camera = await handler.run_in_executor(
            partial(
                handler._get_camera,  # pylint: disable=protected-access
                camera_identifier,
                failed=failed,
            )
        )
        if camera:
            return True
        handler.response_error(
            HTTPStatus.NOT_FOUND,
            reason=f"Camera {camera_identifier} not found",
        )
        return False

    camera = await handler.run_in_executor(
        partial(
            handler._get_camera,  # pylint: disable=protected-access
            camera_identifier,
            failed=failed,
        )
    )
    if not camera:
        handler.response_error(
            HTTPStatus.NOT_FOUND,
            reason=f"Camera {camera_identifier} not found",
        )
        return False

    if not await handler.run_in_executor(handler.validate_camera_token, camera):
        handler.response_error(HTTPStatus.UNAUTHORIZED, reason="Unauthorized")
        return False
    return True


def _content_type(path: str) -> str:
    """Return content type for a file path."""
    extension = os.path.splitext(path)[1].lower()
    if extension in CONTENT_TYPES:
        return CONTENT_TYPES[extension]
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def _etag(path: str, size: int, mtime: float) -> str:
    """Return an ETag for a resolved file."""
    etag_base = f"{path}:{size}:{mtime}".encode()
    return hashlib.sha256(etag_base).hexdigest()


def _parse_range_header(range_header: str, size: int) -> tuple[int, int]:
    """Parse a single HTTP bytes range."""
    units, _, range_spec = range_header.partition("=")
    if units != "bytes" or "," in range_spec:
        raise FileRangeError

    start_str, _, end_str = range_spec.partition("-")
    if not start_str and not end_str:
        raise FileRangeError

    if start_str:
        start = int(start_str)
        end = int(end_str) if end_str else size - 1
    else:
        suffix_length = int(end_str)
        if suffix_length <= 0:
            raise FileRangeError
        start = max(size - suffix_length, 0)
        end = size - 1

    if start < 0 or end < start or start >= size:
        raise FileRangeError
    return start, min(end, size - 1)


async def _write_file_range(
    handler: BaseAPIHandler,
    file_obj,
    start: int,
    end: int,
) -> None:
    """Write file bytes for the inclusive range."""

    def read_chunk(file_obj, bytes_to_read: int) -> bytes:
        return file_obj.read(min(CHUNK_SIZE, bytes_to_read))

    try:
        file_obj.seek(start)
        bytes_remaining = end - start + 1
        while bytes_remaining > 0:
            chunk = await handler.run_in_executor(read_chunk, file_obj, bytes_remaining)
            if not chunk:
                break
            bytes_remaining -= len(chunk)
            handler.write(chunk)
            await handler.flush()
        handler.finish()
    except OSError:
        LOGGER.exception("Failed while streaming file response")
        raise
    finally:
        await handler.run_in_executor(file_obj.close)


async def serve_resolved_file(
    handler: BaseAPIHandler,
    resolved_file: ResolvedFile,
    *,
    cache_control: str = "public, max-age=86400",
) -> None:
    """Serve a resolved file with basic static-file semantics."""
    try:
        stat_result = await handler.run_in_executor(os.stat, resolved_file.path)
    except FileNotFoundError:
        LOGGER.warning(
            "Resolved file disappeared before serving "
            "(file_id=%s, camera=%s, type=%s/%s, path=%s)",
            resolved_file.file_id,
            resolved_file.camera_identifier,
            resolved_file.category,
            resolved_file.subcategory,
            resolved_file.path,
        )
        handler.response_error(HTTPStatus.NOT_FOUND, reason="File not found")
        return
    except OSError:
        LOGGER.exception("Failed to stat file %s", resolved_file.path)
        handler.response_error(HTTPStatus.INTERNAL_SERVER_ERROR, reason="File error")
        return

    size = stat_result.st_size
    start = 0
    end = size - 1
    status = HTTPStatus.OK

    range_header = handler.request.headers.get("Range")
    if range_header:
        try:
            start, end = await handler.run_in_executor(
                _parse_range_header,
                range_header,
                size,
            )
        except (FileRangeError, ValueError):
            handler.set_status(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            handler.set_header("Content-Range", f"bytes */{size}")
            handler.finish()
            return
        status = HTTPStatus.PARTIAL_CONTENT

    file_obj = None
    if size:
        try:
            file_obj = await handler.run_in_executor(open, resolved_file.path, "rb")
            await handler.run_in_executor(file_obj.seek, start)
        except FileNotFoundError:
            if file_obj is not None:
                await handler.run_in_executor(file_obj.close)
            LOGGER.warning(
                "Resolved file disappeared before opening "
                "(file_id=%s, camera=%s, type=%s/%s, path=%s)",
                resolved_file.file_id,
                resolved_file.camera_identifier,
                resolved_file.category,
                resolved_file.subcategory,
                resolved_file.path,
            )
            handler.response_error(HTTPStatus.NOT_FOUND, reason="File not found")
            return
        except OSError:
            if file_obj is not None:
                await handler.run_in_executor(file_obj.close)
            LOGGER.exception("Failed to open file %s", resolved_file.path)
            handler.response_error(
                HTTPStatus.INTERNAL_SERVER_ERROR, reason="File error"
            )
            return

    content_length = end - start + 1 if size else 0
    handler.set_status(status)
    handler.set_header("Accept-Ranges", "bytes")
    handler.set_header("Cache-Control", cache_control)
    handler.set_header("Content-Type", _content_type(resolved_file.path))
    handler.set_header("Content-Length", str(content_length))
    handler.set_header("Etag", _etag(resolved_file.path, size, stat_result.st_mtime))
    handler.set_header("Last-Modified", formatdate(stat_result.st_mtime, usegmt=True))
    if status == HTTPStatus.PARTIAL_CONTENT:
        handler.set_header("Content-Range", f"bytes {start}-{end}/{size}")

    if size == 0:
        handler.finish()
        return
    assert file_obj is not None  # noqa: S101
    await _write_file_range(handler, file_obj, start, end)


class FilesAPIHandler(BaseAPIHandler):
    """API handler for logical file serving."""

    routes = [
        {
            "path_pattern": r"/files/(?P<file_id>[0-9]+)",
            "supported_methods": ["GET"],
            "method": "get_file",
            "allow_token_parameter": True,
            "requires_auth": False,
        },
    ]

    async def get_file(self, file_id: str) -> None:
        """Get a file by id."""
        resolved_file = await self.run_in_executor(
            resolve_file_id,
            self._get_session,
            self._storage,
            int(file_id),
        )
        if resolved_file is None:
            LOGGER.warning("Returning 404 for unresolved file id %s", file_id)
            self.response_error(HTTPStatus.NOT_FOUND, reason="File not found")
            return

        if not await authorize_file_request(
            self, resolved_file.camera_identifier, failed=True
        ):
            return

        await serve_resolved_file(self, resolved_file)
