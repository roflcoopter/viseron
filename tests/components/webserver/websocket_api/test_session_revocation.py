"""Tests for WebSocket session revocation."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from tornado.httpclient import HTTPRequest
from tornado.testing import gen_test
from tornado.web import create_signed_value
from tornado.websocket import WebSocketClientConnection, websocket_connect

from viseron.components.webserver.const import WEBSOCKET_CONNECTIONS

from tests.components.webserver.common import (
    AUTH_STORAGE_DATA,
    READ_REFRESH_TOKEN_ID,
    READ_USER_ID,
    REFRESH_TOKEN_ID,
    USER_ID,
    TestAppBaseAuth,
)


class TestWebSocketSessionRevocation(TestAppBaseAuth):
    """Verify that revoking a session terminates live WebSocket connections."""

    async def _authenticated_connection(
        self,
        user_id: str = USER_ID,
        refresh_token_id: str = REFRESH_TOKEN_ID,
    ) -> WebSocketClientConnection:
        """Open a WebSocket connection and authenticate it."""
        os.makedirs(
            os.path.dirname(self.webserver.auth._auth_store.path), exist_ok=True
        )
        with open(self.webserver.auth._auth_store.path, "w", encoding="utf-8") as file:
            json.dump(AUTH_STORAGE_DATA, file)

        refresh_token = self.webserver.auth.get_refresh_token(refresh_token_id)
        access_token = self.webserver.auth.generate_access_token(
            refresh_token, "dummy.lan"
        )
        header, payload, signature = access_token.split(".")

        def _cookie(name: str, value: str) -> str:
            signed = create_signed_value(
                self._app.settings["cookie_secret"], name, value
            ).decode()
            return f"{name}={signed};"

        request = HTTPRequest(
            f"ws://127.0.0.1:{self.get_http_port()}/websocket",
            headers={
                "Cookie": (
                    _cookie("refresh_token", refresh_token.token)
                    + f"user={user_id};"
                    + _cookie("signature_cookie", signature)
                )
            },
        )
        conn = await websocket_connect(request)
        assert json.loads(await conn.read_message())["type"] == "auth_required"
        await conn.write_message(
            json.dumps({"type": "auth", "access_token": f"{header}.{payload}"})
        )
        assert json.loads(await conn.read_message())["type"] == "auth_ok"
        return conn

    async def _ping(self, conn: WebSocketClientConnection, command_id: int) -> Any:
        """Send a ping command and return the decoded reply, None if closed."""
        await conn.write_message(json.dumps({"type": "ping", "command_id": command_id}))
        message = await conn.read_message()
        return None if message is None else json.loads(message)

    async def _drain(self, conn: WebSocketClientConnection) -> None:
        """Close the connection and wait for the server to deregister it.

        The webserver shutdown in tearDown blocks on open connections, so every
        test has to leave the connection registry empty.
        """
        conn.close()
        while self.vis.data[WEBSOCKET_CONNECTIONS]:
            await asyncio.sleep(0.01)

    async def _assert_revoked(self, conn: WebSocketClientConnection) -> None:
        """Assert the server proactively terminated the connection.

        Nothing is sent from the client first, so this only passes if the
        revocation itself closed the socket rather than a later command being
        rejected. Long-lived subscriptions keep streaming otherwise.
        """
        message = await conn.read_message()
        assert message is not None, "connection closed without telling the client why"
        assert json.loads(message)["type"] == "auth_failed", message

        assert await conn.read_message() is None, "connection was left open"
        while self.vis.data[WEBSOCKET_CONNECTIONS]:
            await asyncio.sleep(0.01)

    @gen_test(timeout=30)
    async def test_logout_closes_websocket(self) -> None:
        """A logged-out session must not keep answering commands."""
        conn = await self._authenticated_connection()
        assert (await self._ping(conn, 1))["type"] == "pong"

        refresh_token = self.webserver.auth.get_refresh_token(REFRESH_TOKEN_ID)
        self.webserver.auth.delete_refresh_token(refresh_token)

        await self._assert_revoked(conn)

    @gen_test(timeout=30)
    async def test_password_change_closes_websocket(self) -> None:
        """Changing the password must log the user out everywhere."""
        conn = await self._authenticated_connection()
        assert (await self._ping(conn, 1))["type"] == "pong"

        self.webserver.auth.change_password(USER_ID, "new_password")

        await self._assert_revoked(conn)

    @gen_test(timeout=30)
    async def test_revoke_all_closes_websocket(self) -> None:
        """An admin revoking all sessions must cut off live connections."""
        conn = await self._authenticated_connection()
        assert (await self._ping(conn, 1))["type"] == "pong"

        self.webserver.auth.revoke_all_for_user(USER_ID)

        await self._assert_revoked(conn)

    @gen_test(timeout=30)
    async def test_delete_user_closes_websocket(self) -> None:
        """Deleting a user must cut off that user's live connections."""
        conn = await self._authenticated_connection(READ_USER_ID, READ_REFRESH_TOKEN_ID)
        assert (await self._ping(conn, 1))["type"] == "pong"

        self.webserver.auth.delete_user(READ_USER_ID)

        await self._assert_revoked(conn)

    @gen_test(timeout=30)
    async def test_token_rotation_keeps_websocket_alive(self) -> None:
        """A routine token refresh must not disconnect an open session."""
        conn = await self._authenticated_connection()
        assert (await self._ping(conn, 1))["type"] == "pong"

        refresh_token = self.webserver.auth.get_refresh_token(REFRESH_TOKEN_ID)
        rotated = self.webserver.auth.rotate_refresh_token(refresh_token)
        assert rotated is not None
        assert rotated.id != refresh_token.id
        assert rotated.session_id == refresh_token.session_id

        assert (await self._ping(conn, 2))["type"] == "pong"
        await self._drain(conn)

    @gen_test(timeout=30)
    async def test_disabled_user_cannot_send_commands(self) -> None:
        """Disabling a user must stop their open connection serving commands."""
        conn = await self._authenticated_connection()
        assert (await self._ping(conn, 1))["type"] == "pong"

        self.webserver.auth.get_user(USER_ID).enabled = False

        response = await self._ping(conn, 2)
        assert response["type"] == "auth_failed", response
        assert await conn.read_message() is None
        while self.vis.data[WEBSOCKET_CONNECTIONS]:
            await asyncio.sleep(0.01)
