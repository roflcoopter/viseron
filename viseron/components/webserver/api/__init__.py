"""API request handler."""
from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

import tornado.routing

from viseron.components.webserver.api.handlers import APINotFoundHandler

if TYPE_CHECKING:
    from tornado.httputil import HTTPServerRequest
    from tornado.web import Application, _HandlerDelegate

    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


class APIRouter(tornado.routing.Router):
    """Catch-all API Router."""

    def __init__(
        self, vis: Viseron, application: Application, **_kwargs: dict[str, Any]
    ) -> None:
        self._vis = vis
        self._application = application

    def find_handler(
        self, request: HTTPServerRequest, **_kwargs: dict[str, Any]
    ) -> _HandlerDelegate:
        """Route to correct API handler."""
        try:
            api_version = request.path.split("/")[2]
            endpoint = request.path.split("/")[3]
        except IndexError:
            LOGGER.warning(
                f"Invalid API request URL: {request.path}",
                exc_info=True,
            )
            handler = APINotFoundHandler
            return self._application.get_handler_delegate(
                request=request,
                target_class=handler,
                target_kwargs={"vis": self._vis},
            )

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
