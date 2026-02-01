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
    """Get handler for endpoint, supporting nested paths."""
    version_path = Path(__file__).parent / api_version

    if not version_path.is_dir():
        return APINotFoundHandler

    # First try direct file match (e.g., endpoint.py)
    module_path = version_path / f"{endpoint}.py"
    if module_path.is_file():
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

    # Try nested path (e.g., endpoint/sub/file.py)
    # Split endpoint path and look for the deepest matching module
    endpoint_parts = endpoint.split("/")
    for i in range(len(endpoint_parts), 0, -1):
        module_parts = endpoint_parts[:i]
        module_path = version_path.joinpath(*module_parts).with_suffix(".py")

        if module_path.is_file():
            try:
                module_import_path = ".".join(module_parts)
                module = importlib.import_module(
                    f"viseron.components.webserver.api.{api_version}."
                    f"{module_import_path}"
                )

                handler_name = (
                    "".join(part.title() for part in module_parts) + "APIHandler"
                )
                if hasattr(module, handler_name):
                    return getattr(module, handler_name)

            except ImportError as error:
                LOGGER.debug(
                    f"Error importing nested API handler {module_import_path}: {error}",
                )
                continue

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
            # Split path: /api/v1/endpoint/sub/path :
            # ['', 'api', 'v1', 'endpoint', 'sub', 'path']
            path_parts = request.path.split("/")
            api_version = path_parts[2]  # 'v1'
            endpoint = "/".join(path_parts[3:])  # 'endpoint/sub/path'
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
