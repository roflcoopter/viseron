"""Viseron request handler."""
from __future__ import annotations

from typing import TYPE_CHECKING

import tornado.web

if TYPE_CHECKING:
    from viseron import Viseron


class ViseronRequestHandler(tornado.web.RequestHandler):
    """Base request handler."""

    def initialize(self, vis: Viseron):
        """Initialize request handler."""
        self._vis = vis
