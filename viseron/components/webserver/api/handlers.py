"""API handlers."""
from __future__ import annotations

import inspect
import json
import logging
from functools import partial
from http import HTTPStatus
from re import Match, Pattern
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast

import tornado.routing
import voluptuous as vol
from voluptuous.humanize import humanize_error
from voluptuous.schema_builder import Schema

from viseron.components.webserver.api.const import API_BASE
from viseron.components.webserver.auth import Role
from viseron.components.webserver.request_handler import ViseronRequestHandler
from viseron.helpers.json import JSONEncoder

if TYPE_CHECKING:
    from typing_extensions import NotRequired

    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

METHOD_ALLOWED_ROLES = {
    "GET": [Role.ADMIN, Role.WRITE, Role.READ],
    "POST": [Role.ADMIN, Role.WRITE],
    "PUT": [Role.ADMIN, Role.WRITE],
    "DELETE": [Role.ADMIN, Role.WRITE],
}


class Route(TypedDict):
    """Routes type."""

    path_pattern: str | Pattern
    supported_methods: list[Literal["GET", "POST", "PUT", "DELETE"]]
    method: str
    requires_auth: NotRequired[bool]
    requires_camera_token: NotRequired[bool]
    requires_role: NotRequired[list[Role]]
    allow_token_parameter: NotRequired[bool]
    json_body_schema: NotRequired[Schema]
    request_arguments_schema: NotRequired[Schema]


class BaseAPIHandler(ViseronRequestHandler):
    """Base handler for all API endpoints."""

    routes: list[Route] = []

    def initialize(self, vis: Viseron) -> None:
        """Initialize."""
        super().initialize(vis)
        self.route: Route = {}  # type: ignore[typeddict-item]
        self.request_arguments: dict[str, Any] = {}
        self.json_body = {}
        self.browser_request = False

    @property
    def json_body(self) -> dict[str, Any]:
        """Return JSON body."""
        return self._json_body

    @json_body.setter
    def json_body(self, value) -> None:
        """Set JSON body."""
        self._json_body = value

    async def response_success(
        self, *, status: HTTPStatus = HTTPStatus.OK, response=None, headers=None
    ) -> None:
        """Send successful response."""

        def _json_dumps() -> str:
            return partial(json.dumps, cls=JSONEncoder, allow_nan=False)(response)

        if response is None:
            response = {"success": True}
        self.set_status(status)

        if headers:
            for header, value in headers.items():
                await self.run_in_executor(self.set_header, header, value)

        if isinstance(response, dict):
            self.finish(await self.run_in_executor(_json_dumps))
            return

        self.finish(response)

    def response_error(self, status_code: HTTPStatus, reason: str) -> None:
        """Send error response."""
        self.set_status(status_code, reason=reason.replace("\n", ""))
        response = {"status": status_code, "error": reason}
        self.finish(response)

    def handle_endpoint_not_found(self) -> None:
        """Return 404."""
        self.response_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def handle_method_not_allowed(self) -> None:
        """Return 405."""
        self.response_error(
            HTTPStatus.METHOD_NOT_ALLOWED, f"Method '{self.request.method}' not allowed"
        )

    def validate_json_body(
        self, route: Route
    ) -> tuple[Literal[False], str] | tuple[Literal[True], None]:
        """Validate JSON body."""
        if schema := route.get("json_body_schema", None):
            try:
                json_body = json.loads(self.request.body)
            except json.JSONDecodeError:
                return False, f"Invalid JSON in body: {self.request.body.decode()}"

            try:
                self.json_body = schema(json_body)
            except vol.Invalid as err:
                LOGGER.error(
                    f"Invalid body: {self.request.body.decode()}",
                    exc_info=True,
                )
                return (
                    False,
                    "Invalid body: {}. {}".format(
                        self.request.body.decode(),
                        humanize_error(json_body, err),
                    ),
                )
        return True, None

    def _construct_jwt_from_header_and_cookies(self) -> str | None:
        """Construct JWT from Header and Cookies."""
        signature = self.get_secure_cookie("signature_cookie")
        if signature is None:
            return None
        jwt_header_payload = self.request.headers.get("Authorization", None)
        if jwt_header_payload is None:
            return None
        return jwt_header_payload + "." + signature.decode()

    def _construct_jwt_from_parameter_and_cookies(self) -> str | None:
        """Construct JWT from Query parameter 'token' and Cookies."""
        signature = self.get_secure_cookie("signature_cookie")
        if signature is None:
            return None
        jwt_header_payload = self.get_argument("token", None)
        if jwt_header_payload is None:
            return None
        return "Bearer " + jwt_header_payload + "." + signature.decode()

    def validate_auth_header(self) -> bool:
        """Validate auth header."""
        # Call is coming from browser? Construct the JWT from the cookies
        auth_header = None
        if self.request.headers.get("X-Requested-With", "") == "XMLHttpRequest":
            self.browser_request = True
            auth_header = self._construct_jwt_from_header_and_cookies()
        # Route allows JWT Header + Payload in URL parameter
        if auth_header is None and self.route.get("allow_token_parameter", False):
            auth_header = self._construct_jwt_from_parameter_and_cookies()
        # Header could not be constructed from cookies or URL parameter
        if auth_header is None:
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

    def _allow_token_parameter(self, schema: Schema, route: Route) -> Schema:
        """Allow token parameter in schema."""
        if route.get("allow_token_parameter", False):
            try:
                schema = schema.extend({vol.Optional("token"): str})
            except AssertionError:
                LOGGER.warning(
                    "Schema is not a dict, cannot extend with token parameter "
                    "for route %s",
                    self.request.uri,
                )
        return schema

    def _path_match(self, route: Route) -> Match[str] | None:
        """Check if path matches."""
        path_match = tornado.routing.PathMatches(f"{API_BASE}{route['path_pattern']}")
        return path_match.regex.match(self.request.path)

    def _get_params(self, route: Route) -> dict[str, Any] | None:
        path_match = tornado.routing.PathMatches(f"{API_BASE}{route['path_pattern']}")
        return path_match.match(self.request)

    async def route_request(self) -> None:
        """Route request to correct API endpoint."""
        unsupported_method = False

        for route in self.routes:
            if await self.run_in_executor(self._path_match, route):
                if self.request.method not in route["supported_methods"]:
                    unsupported_method = True
                    continue

                self.route = route
                if self._webserver.auth and route.get("requires_auth", True):
                    if not await self.run_in_executor(self.validate_auth_header):
                        self.response_error(
                            HTTPStatus.UNAUTHORIZED, reason="Authentication required"
                        )
                        return

                    if not self.current_user:
                        self.response_error(
                            HTTPStatus.UNAUTHORIZED, reason="User not set"
                        )
                        return

                    if requires_role := route.get("requires_role", None):
                        if self.current_user.role not in requires_role:
                            LOGGER.debug(
                                "Request with invalid permissions, endpoint requires"
                                f" {requires_role}, user has role"
                                f" {self.current_user.role}"
                            )
                            self.response_error(
                                HTTPStatus.FORBIDDEN, reason="Insufficient permissions"
                            )
                            return
                    else:
                        if (
                            self.current_user.role
                            not in METHOD_ALLOWED_ROLES[self.request.method]
                        ):
                            LOGGER.debug(
                                "Request with invalid permissions, endpoint requires"
                                f" {METHOD_ALLOWED_ROLES[self.request.method]}, user"
                                f" has role {self.current_user.role}"
                            )
                            self.response_error(
                                HTTPStatus.FORBIDDEN, reason="Insufficient permissions"
                            )
                            return

                params = await self.run_in_executor(self._get_params, route)
                if params is None:
                    params = {}

                request_arguments = {
                    k: self.get_argument(k) for k in self.request.arguments
                }
                if schema := route.get("request_arguments_schema", None):
                    try:
                        # Implicitly allow token parameter if route allows it
                        schema = self._allow_token_parameter(schema, route)
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

                path_args = [param.decode() for param in params.get("path_args", [])]
                path_kwargs = params.get("path_kwargs", {})
                for key, value in path_kwargs.items():
                    path_kwargs[key] = value.decode()

                if self._webserver.auth and route.get("requires_camera_token", False):
                    camera_identifier = path_kwargs.get("camera_identifier", None)
                    if not camera_identifier:
                        self.response_error(
                            HTTPStatus.BAD_REQUEST,
                            reason="Missing camera identifier in request",
                        )
                        return

                    camera = await self.run_in_executor(
                        self._get_camera, camera_identifier
                    )
                    if not camera:
                        self.response_error(
                            HTTPStatus.NOT_FOUND,
                            reason=f"Camera {camera_identifier} not found",
                        )
                        return

                    if not await self.run_in_executor(
                        self.validate_camera_token, camera
                    ):
                        self.response_error(
                            HTTPStatus.UNAUTHORIZED,
                            reason="Unauthorized",
                        )
                        return

                result, reason = await self.run_in_executor(
                    self.validate_json_body, route
                )
                if not result:
                    self.response_error(
                        HTTPStatus.BAD_REQUEST,
                        reason=cast(str, reason),
                    )
                    return

                LOGGER.debug(
                    (
                        "Routing to {}.{}(*args={}, **kwargs={}, request_arguments={})"
                    ).format(
                        self.__class__.__name__,
                        route["method"],
                        path_args,
                        path_kwargs,
                        self.request_arguments,
                    ),
                )
                try:
                    func = getattr(self, route["method"])
                    if inspect.iscoroutinefunction(func):
                        return await func(*path_args, **path_kwargs)
                    return func(*path_args, **path_kwargs)
                except Exception as error:  # pylint: disable=broad-except
                    LOGGER.error(
                        f"Error in API {self.__class__.__name__}."
                        f"{self.route['method']}: "
                        f"{str(error)}",
                        exc_info=True,
                    )
                    self.response_error(
                        HTTPStatus.INTERNAL_SERVER_ERROR, reason="Internal server error"
                    )
                    return

        if unsupported_method:
            LOGGER.warning(f"Method not allowed for URI: {self.request.uri}")
            self.handle_method_not_allowed()
        else:
            LOGGER.warning(f"Endpoint not found for URI: {self.request.uri}")
            self.handle_endpoint_not_found()

    async def delete(self) -> None:
        """Route DELETE requests."""
        await self.route_request()

    async def get(self) -> None:
        """Route GET requests."""
        await self.route_request()

    async def post(self) -> None:
        """Route POST requests."""
        await self.route_request()

    async def put(self) -> None:
        """Route PUT requests."""
        await self.route_request()


class APINotFoundHandler(BaseAPIHandler):
    """Default handler."""

    async def get(self) -> None:
        """Catch all methods."""
        self.response_error(HTTPStatus.NOT_FOUND, "Endpoint not found")
