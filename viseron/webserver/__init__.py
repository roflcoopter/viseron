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

    def open(self):
        """Called on websocket open."""
        LOGGER.debug("WebSocket opened")
        tornado.ioloop.IOLoop.current().add_future(
            self.get_data(), lambda f: self.close()
        )

    def on_message(self, message):
        """Called on websocket message."""
        self.write_message("You said: " + message)

    def on_close(self):  # pylint: disable=no-self-use
        """Called on websocket close."""
        LOGGER.debug("WebSocket closed")


class RegularSocketHandler(tornado.web.RequestHandler):
    """Socket handler."""

    def get(self):
        """GET request."""
        self.render("assets/index.html")


class WebServer(threading.Thread):
    """Webserver."""

    def __init__(self):
        super().__init__(name="WebServer")
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
            ],
            debug=True,
        )

    def run(self):
        """Start ioloop."""
        self.ioloop.start()
