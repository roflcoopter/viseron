"""Config API Handler."""
import logging

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.const import CONFIG_PATH

LOGGER = logging.getLogger(__name__)


class ConfigAPIHandler(BaseAPIHandler):
    """Handler for API calls related to config."""

    routes = [
        {
            "path_pattern": r"/config",
            "supported_methods": ["GET"],
            "method": "get_config",
        },
    ]

    async def get_config(self) -> None:
        """Return Viseron config."""

        def read_config() -> str:
            with open(CONFIG_PATH, encoding="utf-8") as config_file:
                return config_file.read()

        config = await self.run_in_executor(read_config)
        self.response_success(response=config)
