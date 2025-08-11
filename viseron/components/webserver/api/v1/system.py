"""System API handler."""

import logging

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import Role

LOGGER = logging.getLogger(__name__)


class SystemAPIHandler(BaseAPIHandler):
    """Handler for API calls related to the system."""

    routes = [
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/system/dispatched_events",
            "supported_methods": ["GET"],
            "method": "get_dispatched_events",
        },
    ]

    async def get_dispatched_events(self) -> None:
        """Return dispatched events."""
        self._vis.dispatched_events.sort()
        await self.response_success(
            response={"events": self._vis.dispatched_events},
        )
