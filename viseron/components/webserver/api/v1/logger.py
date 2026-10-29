"""Logger API handler."""

from __future__ import annotations

import datetime
import logging
import os
import re
import time as _time
from typing import Any

import voluptuous as vol

from viseron.components.logger.const import (
    COMPONENT as LOGGER_COMPONENT,
    CONFIG_CAMERAS,
    CONFIG_DEFAULT_LEVEL,
    CONFIG_LOGS,
)
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import Role
from viseron.const import VISERON_LOG_PATH

LOGGER = logging.getLogger(__name__)

LOG_LEVELS = ["critical", "error", "warning", "info", "debug"]
DEFAULT_LINES = 500  # will be chosen at first render of the logger page
MAX_LINES = 5000  # more than this will make requests or page rendering heavy

LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

# "%(asctime)s.%(msecs)03d [%(levelname)-8s] [%(name)s] - %(message)s"
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} "
    r"\d{2}:\d{2}:\d{2}\.\d{3,6})\s+"
    r"\[(?P<level>[A-Z]+)\s*\]\s+"
    r"\[(?P<name>[^\]]+)\]\s+-\s+(?P<message>.*)$"
)


def _server_local_tz() -> datetime.tzinfo:
    """Return the server's local timezone."""
    if _time.daylight:
        return datetime.timezone(
            datetime.timedelta(seconds=-_time.altzone),
            name=_time.tzname[1],
        )
    return datetime.timezone(
        datetime.timedelta(seconds=-_time.timezone),
        name=_time.tzname[0],
    )


_SERVER_LOCAL_TZ = _server_local_tz()


def _parse_log_line(line: str, line_index: int) -> dict[str, Any]:
    """Parse a single log line into structured data."""
    match = LOG_PATTERN.match(line)
    if match:
        timestamp_str = match.group("timestamp")
        level = match.group("level").strip().lower()
        name = match.group("name")
        try:
            dt = datetime.datetime.strptime(
                timestamp_str,
                LOG_DATE_FORMAT,
            ).replace(tzinfo=_SERVER_LOCAL_TZ)
            timestamp_unix_ms = int(dt.timestamp() * 1000)
        except (ValueError, OverflowError):
            timestamp_unix_ms = None
        return {
            "id": f"{timestamp_str}_{level}_{name}_{line_index}",
            "timestamp": timestamp_str,
            "timestamp_unix_ms": timestamp_unix_ms,
            "level": level,
            "name": name,
            "message": match.group("message"),
            "raw": line,
        }
    return {
        "id": f"unparsed_{abs(hash(line)) % 10_000_000}_{line_index}",
        "raw": line,
        "unparsed": True,
    }


def _tail_file(
    filepath: str, lines: int, search: str | None, levels: list[str] | None
) -> list[dict[str, Any]]:
    """Read the last N lines from a log file, with optional filters."""
    if not os.path.exists(filepath):
        return []

    result: list[dict[str, Any]] = []
    count = 0

    with open(filepath, "rb") as f:
        # seek from end for efficiency
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        block_size = 4096
        blocks: list[str] = []

        # read backwards in blocks
        position = file_size
        while position > 0 and count < lines * 2:  # extra for filtering
            read_size = min(block_size, position)
            position -= read_size
            f.seek(position)
            block = f.read(read_size).decode("utf-8", errors="replace")
            blocks.append(block)
            count += block.count("\n")

        raw = "".join(reversed(blocks))

        # If reading started in the middle of the file,
        # discard the incomplete first line.
        if position > 0:
            newline_index = raw.find("\n")
            if newline_index != -1:
                raw = raw[newline_index + 1 :]

        # Ignore the last line if it is currently being written.
        if raw and not raw.endswith("\n"):
            raw = raw.rsplit("\n", 1)[0]

        all_lines = raw.splitlines()

        # Process from the end
        for i, line in enumerate(reversed(all_lines)):
            if not line.strip():
                continue

            parsed = _parse_log_line(line, i)

            # Filter by level
            if levels and parsed.get("level") not in levels:
                continue

            # Filter by search string
            if search:
                if search.lower() not in line.lower():
                    continue

            result.append(parsed)

            if len(result) >= lines:
                break

    return list(reversed(result))


class LoggerAPIHandler(BaseAPIHandler):
    """Handler for API calls related to logger."""

    routes = [
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/logger/logs",
            "supported_methods": ["GET"],
            "method": "get_logs",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("lines", default=DEFAULT_LINES): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=MAX_LINES)
                    ),
                    vol.Optional("search", default=None): vol.Maybe(str),
                    vol.Optional("level", default=None): vol.Maybe(
                        vol.All(vol.Lower, vol.In(LOG_LEVELS))
                    ),
                },
                extra=vol.ALLOW_EXTRA,
            ),
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/logger/config",
            "supported_methods": ["GET"],
            "method": "get_logger_config",
        },
    ]

    async def get_logs(self) -> None:
        """Return parsed log entries from viseron.log."""
        lines: int = self.request_arguments["lines"]
        search: str | None = self.request_arguments.get("search")
        level_filter: str | None = self.request_arguments.get("level")

        levels = [level_filter] if level_filter else None

        def _get_logs() -> dict[str, Any]:
            parsed_lines = _tail_file(VISERON_LOG_PATH, lines, search, levels)
            log_exists = os.path.exists(VISERON_LOG_PATH)
            file_size = os.path.getsize(VISERON_LOG_PATH) if log_exists else 0
            return {
                "logs": parsed_lines,
                "total_lines_returned": len(parsed_lines),
                "requested_lines": lines,
                "file_exists": log_exists,
                "file_size": file_size,
                "filters": {
                    "search": search,
                    "level": level_filter,
                },
            }

        result = await self.run_in_executor(_get_logs)
        await self.response_success(response=result)

    async def get_logger_config(self) -> None:
        """Return current logger configuration."""
        logger_data = self._vis.data.get(LOGGER_COMPONENT, {})
        config = {
            "default_level": logger_data.get(CONFIG_DEFAULT_LEVEL, "info"),
            "logs": logger_data.get(CONFIG_LOGS, {}),
            "cameras": logger_data.get(CONFIG_CAMERAS, {}),
        }
        await self.response_success(response=config)
