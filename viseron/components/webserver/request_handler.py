"""Viseron request handler."""

import tornado.web


class ViseronRequestHandler(tornado.web.RequestHandler):
    """Base request handler."""

    def initialize(self, vis):
        """Initialize request handler."""
        self._vis = vis
