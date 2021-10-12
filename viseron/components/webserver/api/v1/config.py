"""Config API Handler."""
import logging

from viseron.components.webserver.api import BaseAPIHandler
from viseron.components.webserver.const import STATUS_ERROR_INTERNAL
from viseron.config import ViseronConfig

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

    def get_config(self, kwargs):
        """Return Viseron config."""
        try:
            self.response_success(ViseronConfig.raw_config)
            return
        except Exception as error:  # pylint: disable=broad-except
            LOGGER.error(
                f"Error in API {self.__class__.__name__}.{kwargs['route']['method']}: "
                f"{str(error)}"
            )
            self.response_error(STATUS_ERROR_INTERNAL, reason=str(error))
