"""API request handler."""
from __future__ import annotations

import importlib
import json
import logging
from functools import partial
from typing import TYPE_CHECKING, Any

import tornado.routing
import voluptuous as vol
from voluptuous.humanize import humanize_error

from viseron.components.webserver.const import (
    STATUS_ERROR_ENDPOINT_NOT_FOUND,
    STATUS_ERROR_INTERNAL,
    STATUS_ERROR_METHOD_NOT_ALLOWED,
    STATUS_SUCCESS,
)
from viseron.components.webserver.not_found_handler import NotFoundHandler
from viseron.components.webserver.request_handler import ViseronRequestHandler
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.exceptions import DomainNotRegisteredError
from viseron.helpers.json import JSONEncoder

if TYPE_CHECKING:
    from viseron import Viseron

API_BASE = "/api/v1"

LOGGER = logging.getLogger(__name__)


class BaseAPIHandler(ViseronRequestHandler):
    """Base handler for all API endpoints."""

    routes: list[dict[str, Any]] = []

    def initialize(self, vis: Viseron):
        """Initialize."""
        super().initialize(vis)
        self.route: dict[str, Any] = {}
        self.request_arguments: dict[str, str] = {}

    def response_success(self, response=None, headers=None):
        """Send successful response."""
        if response is None:
            response = {"success": True}
        self.set_status(STATUS_SUCCESS)

        if headers:
            for header, value in headers.items():
                self.set_header(header, value)

        if isinstance(response, dict):
            self.finish(partial(json.dumps, cls=JSONEncoder, allow_nan=False)(response))
            return

        self.finish(response)

    def response_error(self, status_code, reason):
        """Send error response."""
        self.set_status(status_code, reason=reason.replace("\n", ""))
        response = {"error": f"{status_code}: {reason}"}
        self.finish(response)

    def handle_endpoint_not_found(self):
        """Return 404."""
        response = {"error": f"{STATUS_ERROR_ENDPOINT_NOT_FOUND}: Endpoint not found"}
        self.set_status(STATUS_ERROR_ENDPOINT_NOT_FOUND)
        self.finish(response)

    def handle_method_not_allowed(self):
        """Return 405."""
        response = {
            "error": (
                f"{STATUS_ERROR_METHOD_NOT_ALLOWED}: "
                f"Method '{self.request.method}' not allowed"
            )
        }
        self.set_status(STATUS_ERROR_METHOD_NOT_ALLOWED)
        self.finish(response)

    def route_request(self):
        """Route request to correct API endpoint."""
        unsupported_method = False

        for route in self.routes:
            path_match = tornado.routing.PathMatches(
                f"{API_BASE}{route['path_pattern']}"
            )
            if path_match.regex.match(self.request.path):
                if self.request.method not in route["supported_methods"]:
                    unsupported_method = True
                    continue

                params = path_match.match(self.request)
                request_arguments = {
                    k: self.get_argument(k) for k in self.request.arguments
                }
                if schema := route.get("request_arguments_schema", None):
                    try:
                        self.request_arguments = schema(request_arguments)
                    except vol.Invalid as err:
                        LOGGER.error(
                            f"Invalid request arguments: {request_arguments}",
                            exc_info=True,
                        )
                        self.response_error(
                            STATUS_ERROR_INTERNAL,
                            reason="Invalid request arguments: {}. {}".format(
                                request_arguments,
                                humanize_error(request_arguments, err),
                            ),
                        )
                        return

                path_args = [param.decode() for param in params.get("path_args", [])]
                path_kwargs = params.get("path_kwargs", [])
                for key, value in path_kwargs.items():
                    path_kwargs[key] = value.decode()
                LOGGER.debug(
                    "Routing to {}.{}(*args={}, **kwargs={})".format(
                        self.__class__.__name__,
                        route.get("method"),
                        path_args,
                        path_kwargs,
                    ),
                )
                self.route = route
                try:
                    getattr(self, route.get("method"))(*path_args, **path_kwargs)
                    return
                except Exception as error:  # pylint: disable=broad-except
                    LOGGER.error(
                        f"Error in API {self.__class__.__name__}."
                        f"{self.route['method']}: "
                        f"{str(error)}",
                        exc_info=True,
                    )
                    self.response_error(STATUS_ERROR_INTERNAL, reason=str(error))
                    return

        if unsupported_method:
            LOGGER.warning(f"Method not allowed for URI: {self.request.uri}")
            self.handle_method_not_allowed()
        else:
            LOGGER.warning(f"Endpoint not found for URI: {self.request.uri}")
            self.handle_endpoint_not_found()

    def _get_camera(self, camera_identifier: str):
        """Get camera instance."""
        try:
            return self._vis.get_registered_domain(CAMERA_DOMAIN, camera_identifier)
        except DomainNotRegisteredError:
            return None

    def delete(self, _path):
        """Route DELETE requests."""
        self.route_request()

    def get(self, _path):
        """Route GET requests."""
        self.route_request()

    def post(self, _path):
        """Route POST requests."""
        self.route_request()

    def put(self, _path):
        """Route PUT requests."""
        self.route_request()


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
            handler = NotFoundHandler
        except ModuleNotFoundError as error:
            LOGGER.warning(
                f"Error importing API endpoint module: {error}", exc_info=True
            )
            handler = NotFoundHandler

        # Return handler
        return self._application.get_handler_delegate(
            request=request,
            target_class=handler,
            target_kwargs={"vis": self._vis},
            path_args=[request.path],
        )
