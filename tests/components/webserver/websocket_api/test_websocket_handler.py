"""Tests for the WebSocket handler."""

from __future__ import annotations

import asyncio
import json
import threading

from tornado.testing import gen_test
from tornado.websocket import websocket_connect

from viseron.components.webserver.const import WEBSOCKET_CONNECTIONS

from tests.components.webserver.common import TestAppBaseNoAuth


class TestWebSocketHandler(TestAppBaseNoAuth):
    """Test the WebSocket handler."""

    @gen_test(timeout=30)
    async def test_send_message_from_thread(self) -> None:
        """Messages sent from worker threads must reach the client."""
        conn = await websocket_connect(
            f"ws://127.0.0.1:{self.get_http_port()}/websocket"
        )
        assert json.loads(await conn.read_message())["type"] == "auth_not_required"
        handler = self.vis.data[WEBSOCKET_CONNECTIONS][0]

        thread = threading.Thread(
            target=handler.send_message, args=({"type": "from_thread"},)
        )
        thread.start()
        thread.join()

        message = await asyncio.wait_for(conn.read_message(), timeout=5)
        assert message is not None
        assert json.loads(message)["type"] == "from_thread"

        conn.close()
        while self.vis.data[WEBSOCKET_CONNECTIONS]:
            await asyncio.sleep(0.01)
