"""Test the API handlers."""

import json
from http import HTTPStatus
from unittest.mock import PropertyMock, patch

import tornado.web
import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import Group, User

from tests.common import MockCamera
from tests.components.webserver.common import TestAppBaseAuth


class DummyAPIHandler(BaseAPIHandler):
    """Test handler."""

    routes = [
        {
            "path_pattern": r"/test",
            "supported_methods": ["GET", "DELETE"],
            "method": "test_get",
        },
        {
            "path_pattern": r"/allow_token_parameter",
            "requires_auth": True,
            "allow_token_parameter": True,
            "supported_methods": ["GET"],
            "method": "test_get",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Required("test_key"): str,
                }
            ),
        },
        {
            "path_pattern": r"/requires_group",
            "supported_methods": ["GET"],
            "method": "test_get",
            "requires_group": [Group.WRITE],
        },
        {
            "requires_auth": False,
            "path_pattern": r"/no_auth",
            "supported_methods": ["GET"],
            "method": "test_get",
        },
        {
            "requires_auth": False,
            "path_pattern": r"/json_body_schema",
            "supported_methods": ["POST"],
            "method": "test_get",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("test_key"): str,
                }
            ),
        },
        {
            "requires_auth": False,
            "path_pattern": r"/request_arguments",
            "supported_methods": ["GET"],
            "method": "test_get",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Required("test_key"): str,
                }
            ),
        },
        {
            "requires_auth": False,
            "requires_camera_token": True,
            "path_pattern": (
                r"/camera/(?P<camera_identifier>[A-Za-z0-9_]+)/requires_camera_token"
            ),
            "supported_methods": ["GET"],
            "method": "test_camera_identifier",
        },
        {
            "requires_auth": False,
            "requires_camera_token": True,
            "path_pattern": r"/camera/requires_camera_token",
            "supported_methods": ["GET"],
            "method": "test_camera_identifier",
        },
        {
            "requires_auth": False,
            "path_pattern": r"/error",
            "supported_methods": ["GET"],
            "method": "test_error",
        },
    ]

    def test_get(self):
        """Handle get request."""
        self.write({"test": "test"})

    async def test_camera_identifier(self, camera_identifier):
        """Handle request with camera_identifier."""
        await self.response_success(response={"camera_identifier": camera_identifier})

    def test_error(self):
        """Handle error."""
        raise ValueError("Test error")


class TestBaseAPIHandler(TestAppBaseAuth):
    """Test the BaseAPIHandler class."""

    def get_app(self):
        """Return an app with fake endpoints."""
        return tornado.web.Application(
            [
                (
                    r"/.*",
                    DummyAPIHandler,
                    {"vis": self.vis},
                )
            ],
            cookie_secret="dummy_secret",
        )

    def test_method_not_allowed(self):
        """Test method not allowed."""
        response = self.fetch("/api/v1/test", method="POST", body="test")
        assert response.code == HTTPStatus.METHOD_NOT_ALLOWED
        assert json.loads(response.body) == {
            "error": "Method 'POST' not allowed",
            "status": HTTPStatus.METHOD_NOT_ALLOWED,
        }

    def test_endpoint_not_found(self):
        """Test endpoint not found."""
        response = self.fetch("/api/v1/does_not_exist", method="GET")
        assert response.code == HTTPStatus.NOT_FOUND
        assert json.loads(response.body) == {
            "error": "Endpoint not found",
            "status": HTTPStatus.NOT_FOUND,
        }

    def test_invalid_auth(self):
        """Test endpoint with requires auth setting."""
        response = self.fetch("/api/v1/test", method="GET")
        assert response.code == HTTPStatus.UNAUTHORIZED
        assert json.loads(response.body) == {
            "error": "Authentication required",
            "status": HTTPStatus.UNAUTHORIZED,
        }

    def test_no_auth(self):
        """Test endpoint with requires_auth=False setting."""
        response = self.fetch("/api/v1/no_auth", method="GET")
        assert response.code == HTTPStatus.OK
        assert json.loads(response.body) == {"test": "test"}

    def test_requires_group(self):
        """Test endpoint with overridden requires_group setting."""
        with patch(
            "viseron.components.webserver.api.handlers.BaseAPIHandler.validate_auth_header",  # pylint: disable=line-too-long
            return_value=True,
        ), patch(
            "viseron.components.webserver.request_handler.ViseronRequestHandler.current_user",  # pylint: disable=line-too-long
            new_callable=PropertyMock,
            return_value=User(
                name="Test",
                username="test",
                password="test",
                group=Group.READ,
            ),
        ):
            response = self.fetch("/api/v1/requires_group", method="GET")
            assert response.code == HTTPStatus.FORBIDDEN
            assert json.loads(response.body) == {
                "error": "Insufficient permissions",
                "status": HTTPStatus.FORBIDDEN,
            }

    def test_requires_group_default(self):
        """Test endpoint with default requires_group setting."""
        with patch(
            "viseron.components.webserver.api.handlers.BaseAPIHandler.validate_auth_header",  # pylint: disable=line-too-long
            return_value=True,
        ), patch(
            "viseron.components.webserver.request_handler.ViseronRequestHandler.current_user",  # pylint: disable=line-too-long
            new_callable=PropertyMock,
            return_value=User(
                name="Test",
                username="test",
                password="test",
                group=Group.READ,
            ),
        ):
            response = self.fetch("/api/v1/test", method="DELETE")
            assert response.code == HTTPStatus.FORBIDDEN
            assert json.loads(response.body) == {
                "error": "Insufficient permissions",
                "status": HTTPStatus.FORBIDDEN,
            }

    def test_json_body_schema(self):
        """Test endpoint with json_body_schema setting."""
        response = self.fetch(
            "/api/v1/json_body_schema",
            method="POST",
            body=json.dumps({"test_key": "test"}),
        )
        assert response.code == HTTPStatus.OK
        assert json.loads(response.body) == {"test": "test"}

    def test_json_body_schema_invalid(self):
        """Test endpoint with json_body_schema setting and failed schema validation."""
        response = self.fetch(
            "/api/v1/json_body_schema",
            method="POST",
            body=json.dumps({"invalid_key": "test"}),
        )
        assert response.code == HTTPStatus.BAD_REQUEST
        body = json.loads(response.body)
        assert "Invalid body" in body["error"]
        assert body["status"] == HTTPStatus.BAD_REQUEST

    def test_json_body_invalid(self):
        """Test endpoint with json_body_schema setting and invalid JSON."""
        response = self.fetch(
            "/api/v1/json_body_schema",
            method="POST",
            body="invalid_json",
        )
        assert response.code == HTTPStatus.BAD_REQUEST
        body = json.loads(response.body)
        assert "Invalid JSON in body" in body["error"]
        assert body["status"] == HTTPStatus.BAD_REQUEST

    def test_request_arguments_schema(self):
        """Test endpoint with request_arguments_schema setting."""
        response = self.fetch(
            "/api/v1/request_arguments?test_key=test",
            method="GET",
        )
        assert response.code == HTTPStatus.OK
        assert json.loads(response.body) == {"test": "test"}

    def test_request_arguments_schema_invalid(self):
        """Test endpoint with request_arguments_schema setting."""
        response = self.fetch(
            "/api/v1/request_arguments?invalid_key=test",
            method="GET",
        )
        assert response.code == HTTPStatus.BAD_REQUEST
        body = json.loads(response.body)
        assert "Invalid request arguments" in body["error"]
        assert body["status"] == HTTPStatus.BAD_REQUEST

    def test_requires_camera_token(self):
        """Test endpoint with requires_camera_token setting."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        with patch(
            "viseron.components.webserver.api.handlers.BaseAPIHandler._get_camera",
            return_value=mocked_camera,
        ):
            response = self.fetch_with_auth(
                "/api/v1/camera/test_camera_identifier/requires_camera_token?access_token=test_access_token",  # pylint: disable=line-too-long
                method="GET",
            )
            assert response.code == HTTPStatus.OK
            assert json.loads(response.body) == {
                "camera_identifier": "test_camera_identifier",
            }

    def test_requires_camera_token_cookie(self):
        """Test endpoint with requires_camera_token setting using cookie based auth."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        with patch(
            "viseron.components.webserver.api.handlers.BaseAPIHandler._get_camera",
            return_value=mocked_camera,
        ):
            response = self.fetch_with_auth(
                "/api/v1/camera/test_camera_identifier/requires_camera_token",
                method="GET",
            )
            assert response.code == HTTPStatus.OK
            assert json.loads(response.body) == {
                "camera_identifier": "test_camera_identifier",
            }

    def test_requires_camera_token_invalid(self):
        """Test endpoint with requires_camera_token setting."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        with patch(
            "viseron.components.webserver.api.handlers.BaseAPIHandler._get_camera",
            return_value=mocked_camera,
        ):
            response = self.fetch_with_auth(
                "/api/v1/camera/test_camera_identifier/requires_camera_token?access_token=invalid_access_token",  # pylint: disable=line-too-long
                method="GET",
            )
            assert response.code == HTTPStatus.UNAUTHORIZED
            assert json.loads(response.body) == {
                "error": "Unauthorized",
                "status": HTTPStatus.UNAUTHORIZED,
            }

    def test_requires_camera_token_missing_identifier(self):
        """Test endpoint with requires_camera_token setting with missing identifier."""
        response = self.fetch_with_auth(
            "/api/v1/camera/requires_camera_token",
            method="GET",
        )
        assert response.code == HTTPStatus.BAD_REQUEST
        assert json.loads(response.body) == {
            "error": "Missing camera identifier in request",
            "status": HTTPStatus.BAD_REQUEST,
        }

    def test_requires_camera_token_missing_camera(self):
        """Test endpoint with requires_camera_token setting with missing camera."""
        response = self.fetch_with_auth(
            "/api/v1/camera/test_camera_identifier/requires_camera_token",
            method="GET",
        )
        assert response.code == HTTPStatus.NOT_FOUND
        assert json.loads(response.body) == {
            "error": "Camera test_camera_identifier not found",
            "status": HTTPStatus.NOT_FOUND,
        }

    def test_error(self):
        """Test endpoint raising an error."""
        response = self.fetch("/api/v1/error")
        assert response.code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert json.loads(response.body) == {
            "error": "Internal server error",
            "status": HTTPStatus.INTERNAL_SERVER_ERROR,
        }

    def test_allow_token_parameter(self):
        """Test endpoint with allow_token_parameter setting."""
        response = self.fetch_with_auth(
            "/api/v1/allow_token_parameter?test_key=test",
            method="GET",
            token_parameter=True,
        )
        assert response.code == HTTPStatus.OK

        # Should work with normal access token as well
        response = self.fetch_with_auth(
            "/api/v1/allow_token_parameter?test_key=test",
            method="GET",
            token_parameter=False,
        )
        assert response.code == HTTPStatus.OK

    def test_allow_token_parameter_missing(self):
        """Test endpoint with allow_token_parameter setting."""
        response = self.fetch_with_auth(
            "/api/v1/allow_token_parameter?test_key=test",
            method="GET",
            token_parameter=False,
            headers={"Authorization": "Bearer test_access_token"},
        )
        assert response.code == HTTPStatus.UNAUTHORIZED
