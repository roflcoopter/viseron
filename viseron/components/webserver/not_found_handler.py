"""Handler for unknown requests."""

import tornado.web

from viseron.components.webserver.const import PATH_404


class NotFoundHandler(tornado.web.RequestHandler):
    """Default handler."""

    def get(self) -> None:
        """Catch all methods."""
        self.set_status(404)
        self.render(PATH_404)
