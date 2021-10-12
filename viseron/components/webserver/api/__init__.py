"""API request handler."""
import importlib
import logging
import re
from typing import Any, Dict, List

import tornado.routing
from tornado.web import RequestHandler

from viseron.components.webserver.const import (
    STATUS_ERROR_ENDPOINT_NOT_FOUND,
    STATUS_ERROR_METHOD_NOT_ALLOWED,
    STATUS_SUCCESS,
)
from viseron.components.webserver.not_found_handler import NotFoundHandler

LOGGER = logging.getLogger(__name__)


class BaseAPIHandler(RequestHandler):
    """Base handler for all API endpoints."""

    routes: List[Dict[str, Any]] = []

    def response_success(self, response=None):
        """Send successful response."""
        if response is None:
            response = {"success": True}
        self.set_status(STATUS_SUCCESS)
        self.finish(response)

    def response_error(self, status_code, reason):
        """Send error response."""
        self.set_status(status_code, reason=reason)
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
        endpoint = re.sub("^/api/.*/", "/", self.request.uri)

        for route in self.routes:
            if re.match(route["path_pattern"], endpoint):
                if self.request.method not in route["supported_methods"]:
                    unsupported_method = True
                    continue

                LOGGER.debug(
                    "Routing to {}.{}()".format(
                        self.__class__.__name__, route.get("method")
                    ),
                )
                kwargs = {"route": route}
                getattr(self, route.get("method"))(kwargs)
                return

        if unsupported_method:
            LOGGER.warning(f"Method not allowed for URI: {self.request.uri}")
            self.handle_method_not_allowed()
        else:
            LOGGER.warning(f"Endpoint not found for URI: {self.request.uri}")
            self.handle_endpoint_not_found()

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

    def __init__(self, application, **_kwargs):
        self._application = application

    def find_handler(self, request, **_kwargs):
        """Route to correct API handler."""
        api_version = request.path.split("/")[2]
        endpoint = request.path.split("/")[3]
        endpoint_handler = f"{endpoint.title()}APIHandler"

        try:
            handler = getattr(
                importlib.import_module(
                    f"viseron.webserver.api.{api_version}".format(api_version)
                ),
                endpoint_handler,
            )
        except AttributeError:
            LOGGER.warning(
                f"Unable to find handler for path: {request.path}",
                exc_info=True,
            )
            handler = NotFoundHandler

        # Return handler
        return self._application.get_handler_delegate(
            request,
            handler,
            path_args=[request.path],
        )
