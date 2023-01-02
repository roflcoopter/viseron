"""Config API Handler."""
import logging

from viseron.components.webserver.api import BaseAPIHandler
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

    def get_config(self):
        """Return Viseron config."""
        with open(CONFIG_PATH, encoding="utf-8") as config_file:
            config = config_file.read()

        self.response_success(config)
