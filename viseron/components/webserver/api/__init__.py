"""API request handler."""
from __future__ import annotations

import importlib
import logging

import tornado.routing

from viseron.components.webserver.api.handlers import APINotFoundHandler

LOGGER = logging.getLogger(__name__)


class APIRouter(tornado.routing.Router):
    """Catch-all API Router."""

    def __init__(self, vis, application, **_kwargs):
        self._vis = vis
        self._application = application

    def find_handler(self, request, **_kwargs):
        """Route to correct API handler."""
        api_version = request.path.split("/")[2]
        endpoint = request.path.split("/")[3]
        endpoint_handler = f"{endpoint.title()}APIHandler"

        try:
            handler = getattr(
                importlib.import_module(
                    f"viseron.components.webserver.api.{api_version}".format(
                        api_version
                    )
                ),
                endpoint_handler,
            )
        except AttributeError:
            LOGGER.warning(
                f"Unable to find handler for path: {request.path}",
                exc_info=True,
            )
            handler = APINotFoundHandler
        except ModuleNotFoundError as error:
            LOGGER.warning(
                f"Error importing API endpoint module: {error}", exc_info=True
            )
            handler = APINotFoundHandler

        # Return handler
        return self._application.get_handler_delegate(
            request=request,
            target_class=handler,
            target_kwargs={"vis": self._vis},
        )
