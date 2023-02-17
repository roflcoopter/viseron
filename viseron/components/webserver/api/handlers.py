"""API handlers."""
from __future__ import annotations

import json
import logging
from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import tornado.routing
import voluptuous as vol
from voluptuous.humanize import humanize_error

from viseron.components.webserver.api.const import API_BASE
from viseron.components.webserver.request_handler import ViseronRequestHandler
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.exceptions import DomainNotRegisteredError
from viseron.helpers.json import JSONEncoder

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


class BaseAPIHandler(ViseronRequestHandler):
    """Base handler for all API endpoints."""

    routes: list[dict[str, Any]] = []

    def initialize(self, vis: Viseron):
        """Initialize."""
        super().initialize(vis)
        self.route: dict[str, Any] = {}
        self.request_arguments: dict[str, Any] = {}
        self.json_body: dict[str, Any] = {}
        self.browser_request = False

    def response_success(
        self, *, status: HTTPStatus = HTTPStatus.OK, response=None, headers=None
    ):
        """Send successful response."""
        if response is None:
            response = {"success": True}
        self.set_status(status)

        if headers:
            for header, value in headers.items():
                self.set_header(header, value)

        if isinstance(response, dict):
            self.finish(partial(json.dumps, cls=JSONEncoder, allow_nan=False)(response))
            return

        self.finish(response)

    def response_error(self, status_code: HTTPStatus, reason: str):
        """Send error response."""
        self.set_status(status_code, reason=reason.replace("\n", ""))
        response = {"status": status_code, "error": reason}
        self.finish(response)

    def handle_endpoint_not_found(self):
        """Return 404."""
        self.response_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def handle_method_not_allowed(self):
        """Return 405."""
        self.response_error(
            HTTPStatus.METHOD_NOT_ALLOWED, f"Method '{self.request.method}' not allowed"
        )

    def validate_json_body(self, route):
        """Validate JSON body."""
        if schema := route.get("json_body_schema", None):
            try:
                json_body = json.loads(self.request.body)
            except json.JSONDecodeError:
                self.response_error(
                    HTTPStatus.BAD_REQUEST,
                    reason=f"Invalid JSON in body: {self.request.body.decode()}",
                )
                return False

            try:
                self.json_body = schema(json_body)
            except vol.Invalid as err:
                LOGGER.error(
                    f"Invalid body: {self.request.body}",
                    exc_info=True,
                )
                self.response_error(
                    HTTPStatus.BAD_REQUEST,
                    reason="Invalid body: {}. {}".format(
                        self.request.body,
                        humanize_error(json_body, err),
                    ),
                )
                return False
        return True

    def _construct_jwt_from_cookies(self) -> str | None:
        """Construct JWT from cookies."""
        signature = self.get_secure_cookie("signature_cookie")
        if signature is None:
            return None
        return self.request.headers.get("Authorization", "") + "." + signature.decode()

    def validate_auth_header(self):
        """Validate auth header."""
        # Call is coming from browser? Construct the JWT from the cookies
        if self.request.headers.get("X-Requested-With", "") == "XMLHttpRequest":
            self.browser_request = True
            auth_header = self._construct_jwt_from_cookies()
        else:
            auth_header = self.request.headers.get("Authorization", None)

        if auth_header is None:
            LOGGER.debug("Auth header is missing")
            return False

        # Check correct auth header format
        try:
            auth_type, auth_val = auth_header.split(" ", 1)
        except ValueError:
            LOGGER.debug("Invalid auth header")
            return False
        if auth_type != "Bearer":
            LOGGER.debug(f"Auth type not Bearer: {auth_type}")
            return False

        return self.validate_access_token(
            auth_val, check_refresh_token=self.browser_request
        )

    def route_request(self):
        """Route request to correct API endpoint."""
        unsupported_method = False

        for route in self.routes:
            path_match = tornado.routing.PathMatches(
                f"{API_BASE}{route['path_pattern']}"
            )
            if path_match.regex.match(self.request.path):
                if self._webserver.auth and route.get("requires_auth", True):
                    if not self.validate_auth_header():
                        self.response_error(
                            HTTPStatus.UNAUTHORIZED, reason="Authentication required"
                        )
                        return
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
                            HTTPStatus.BAD_REQUEST,
                            reason="Invalid request arguments: {}. {}".format(
                                request_arguments,
                                humanize_error(request_arguments, err),
                            ),
                        )
                        return

                if not self.validate_json_body(route):
                    return

                path_args = [param.decode() for param in params.get("path_args", [])]
                path_kwargs = params.get("path_kwargs", {})
                for key, value in path_kwargs.items():
                    path_kwargs[key] = value.decode()
                LOGGER.debug(
                    (
                        "Routing to {}.{}(*args={}, **kwargs={}, request_arguments={})"
                    ).format(
                        self.__class__.__name__,
                        route.get("method"),
                        path_args,
                        path_kwargs,
                        self.request_arguments,
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
                    self.response_error(
                        HTTPStatus.INTERNAL_SERVER_ERROR, reason=str(error)
                    )
                    return

        if unsupported_method:
            LOGGER.warning(f"Method not allowed for URI: {self.request.uri}")
            self.handle_method_not_allowed()
        else:
            LOGGER.warning(f"Endpoint not found for URI: {self.request.uri}")
            self.handle_endpoint_not_found()

    def _get_cameras(self):
        """Get all registered camera instances."""
        try:
            return self._vis.get_registered_identifiers(CAMERA_DOMAIN)
        except DomainNotRegisteredError:
            return None

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


class APINotFoundHandler(BaseAPIHandler):
    """Default handler."""

    def get(self, _path):
        """Catch all methods."""
        self.response_error(HTTPStatus.NOT_FOUND, "Endpoint not found")
