"""Viseron webserver."""
import datetime
import logging
import threading

import tornado.gen
import tornado.ioloop
import tornado.web
import tornado.websocket

from viseron.webserver.stream_handler import DynamicStreamHandler, StaticStreamHandler

LOGGER = logging.getLogger(__name__)


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    """Websocket handler."""

    def check_origin(self, origin):  # pylint: disable=unused-argument,no-self-use
        """Check request origin."""
        return True

    @tornado.gen.coroutine
    def get_data(self):
        """Get data."""
        while True:
            LOGGER.debug("Write time")
            try:
                yield self.write_message(
                    {
                        "current_time": datetime.datetime.strftime(
                            datetime.datetime.now(), "%Y-%m-%d %H:%M:%S"
                        )
                    }
                )
                yield tornado.gen.sleep(1)
            except tornado.websocket.WebSocketClosedError:
                break

    def open(self, *_args: str, **_kwargs: str):
        """Websocket open."""
        LOGGER.debug("WebSocket opened")
        tornado.ioloop.IOLoop.current().add_future(
            self.get_data(), lambda f: self.close()
        )

    def on_message(self, message):
        """Websocket message received."""
        self.write_message("You said: " + message)

    def on_close(self):  # pylint: disable=no-self-use
        """Websocket close."""
        LOGGER.debug("WebSocket closed")


class RegularSocketHandler(tornado.web.RequestHandler):
    """Socket handler."""

    def get(self):
        """GET request."""
        self.render("assets/index.html")


class DeprecatedStreamHandler(tornado.web.RequestHandler):
    """Socket handler."""

    def get(self, camera):
        """GET request."""
        LOGGER.warning(
            f"The endpoint /{camera}/stream is deprecated. "
            f"Please use /{camera}/mjpeg-stream instead."
        )
        self.redirect(f"/{camera}/mjpeg-stream")


class NotFoundHandler(tornado.web.RequestHandler):
    """Default handler."""

    def prepare(self):  # pylint: disable=no-self-use
        """Catch all methods."""
        raise tornado.web.HTTPError(404)


class WebServer(threading.Thread):
    """Webserver."""

    def __init__(self):
        super().__init__(name="Tornado WebServer", daemon=True)
        self.application = self.create_application()
        self.application.listen(8888)
        self.ioloop = tornado.ioloop.IOLoop.current()

    @staticmethod
    def create_application():
        """Return tornado web app."""
        return tornado.web.Application(
            [
                (r"/(?P<camera>[A-Za-z0-9_]+)/mjpeg-stream", DynamicStreamHandler),
                (
                    (
                        r"/(?P<camera>[A-Za-z0-9_]+)/static-mjpeg-streams/"
                        r"(?P<mjpeg_stream>[A-Za-z0-9_\-]+)"
                    ),
                    StaticStreamHandler,
                ),
                (r"/ws-stream", RegularSocketHandler),
                (r"/websocket", WebSocketHandler),
                (r"/(?P<camera>[A-Za-z0-9_]+)/stream", DeprecatedStreamHandler),
            ],
            default_handler_class=NotFoundHandler,
            debug=True,
        )

    def run(self):
        """Start ioloop."""
        self.ioloop.start()
        self.ioloop.close()

    def stop(self):
        """Stop ioloop."""
        self.ioloop.stop()
