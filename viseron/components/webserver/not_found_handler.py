"""Handler for unknown requests."""

import tornado.web


class NotFoundHandler(tornado.web.RequestHandler):
    """Default handler."""

    def get(self, _path) -> None:
        """Catch all methods."""
        self.set_status(404)
        self.write("404 Not Found")
