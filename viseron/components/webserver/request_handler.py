"""Viseron request handler."""
from __future__ import annotations

from typing import TYPE_CHECKING

import tornado.web

from viseron.components.webserver.const import COMPONENT

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.webserver import WebServer


class ViseronRequestHandler(tornado.web.RequestHandler):
    """Base request handler."""

    def initialize(self, vis: Viseron):
        """Initialize request handler."""
        self._vis = vis
        self._webserver: WebServer = vis.data[COMPONENT]
