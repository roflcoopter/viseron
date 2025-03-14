"""API request handler."""
from __future__ import annotations

import importlib
import logging
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tornado.routing

from viseron.components.webserver.api.handlers import APINotFoundHandler

if TYPE_CHECKING:
    from tornado.httputil import HTTPServerRequest
    from tornado.web import Application, _HandlerDelegate

    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


@cache
def get_handler(api_version: str, endpoint: str):
    """Get handler for endpoint."""
    version_path = Path(__file__).parent / api_version

    if not version_path.is_dir():
        return APINotFoundHandler

    module_path = version_path / f"{endpoint}.py"
    if not module_path.is_file():
        return APINotFoundHandler

    try:
        module = importlib.import_module(
            f"viseron.components.webserver.api.{api_version}.{endpoint}"
        )
        handler_name = f"{endpoint.title()}APIHandler"
        if hasattr(module, handler_name):
            return getattr(module, handler_name)
    except ImportError as error:
        LOGGER.warning(
            f"Error importing API handler {endpoint}: {error}",
            exc_info=True,
        )
    return APINotFoundHandler


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

        handler = get_handler(api_version, endpoint)
        if handler == APINotFoundHandler:
            LOGGER.warning(
                f"Unable to find handler for path: {request.path}",
            )

        return self._application.get_handler_delegate(
            request=request,
            target_class=handler,
            target_kwargs={"vis": self._vis},
        )
