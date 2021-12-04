"""Viseron webserver."""
import asyncio
import datetime
import logging
import threading

import tornado.gen
import tornado.ioloop
import tornado.web
import tornado.websocket
import voluptuous as vol
from tornado.routing import PathMatches

from viseron import Viseron
from viseron.const import VISERON_SIGNAL_SHUTDOWN

from .api import APIRouter
from .const import PATH_STATIC, PATH_TEMPLATES, PREFIX_STATIC
from .not_found_handler import NotFoundHandler
from .stream_handler import DynamicStreamHandler, StaticStreamHandler
from .ui import (
    AboutHandler,
    CamerasHandler,
    IndexHandler,
    RecordingsHandler,
    SettingsHandler,
)

COMPONENT = "webserver"

CONFIG_PORT = "port"
CONFIG_DEBUG = "debug"

DEFAULT_PORT = 8888
DEFAULT_DEBUG = False

LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.Optional(CONFIG_PORT, default=DEFAULT_PORT): vol.All(
                    int, vol.Range(min=1024, max=49151)
                ),
                vol.Optional(CONFIG_DEBUG, default=DEFAULT_DEBUG): bool,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the webserver component."""
    config = config[COMPONENT]
    webserver = WebServer(vis, config)
    vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, webserver.stop)
    webserver.start()

    return True


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
        self.render("ws_index.html")


class DeprecatedStreamHandler(tornado.web.RequestHandler):
    """Socket handler."""

    def get(self, camera):
        """GET request."""
        LOGGER.warning(
            f"The endpoint /{camera}/stream is deprecated. "
            f"Please use /{camera}/mjpeg-stream instead."
        )
        self.redirect(f"/{camera}/mjpeg-stream")


class IndexRedirect(tornado.web.RequestHandler):
    """Redirect handler for index."""

    def get(self):
        """GET request."""
        self.redirect("/ui/")


class WebServer(threading.Thread):
    """Webserver."""

    def __init__(self, vis, config):
        super().__init__(name="Tornado WebServer", daemon=True)
        self._vis = vis
        self._config = config
        ioloop = asyncio.new_event_loop()
        asyncio.set_event_loop(ioloop)
        application = self.create_application()
        application.listen(config[CONFIG_PORT])
        self._ioloop = tornado.ioloop.IOLoop.current()

    def create_application(self):
        """Return tornado web app."""
        application = tornado.web.Application(
            [
                (
                    r"/(?P<camera>[A-Za-z0-9_]+)/mjpeg-stream",
                    DynamicStreamHandler,
                    {"vis": self._vis},
                ),
                (
                    (
                        r"/(?P<camera>[A-Za-z0-9_]+)/static-mjpeg-streams/"
                        r"(?P<mjpeg_stream>[A-Za-z0-9_\-]+)"
                    ),
                    StaticStreamHandler,
                    {"vis": self._vis},
                ),
                (r"/ws-stream", RegularSocketHandler),
                (r"/websocket", WebSocketHandler),
                (r"/(?P<camera>[A-Za-z0-9_]+)/stream", DeprecatedStreamHandler),
                (r"/ui/", IndexHandler, {"vis": self._vis}),
                (r"/ui/about", AboutHandler, {"vis": self._vis}),
                (r"/ui/cameras", CamerasHandler, {"vis": self._vis}),
                (r"/ui/index", IndexHandler, {"vis": self._vis}),
                (r"/ui/recordings", RecordingsHandler, {"vis": self._vis}),
                (r"/ui/settings", SettingsHandler, {"vis": self._vis}),
                (
                    r"/recordings/(.*)",
                    tornado.web.StaticFileHandler,
                    {"vis": self._vis},
                ),
                (r"/", IndexRedirect, {"vis": self._vis}),
            ],
            default_handler_class=NotFoundHandler,
            template_path=PATH_TEMPLATES,
            static_path=PATH_STATIC,
            static_url_prefix=PREFIX_STATIC,
            debug=self._config[CONFIG_DEBUG],
        )
        application.add_handlers(
            r".*",
            [
                (PathMatches(r"/api/.*"), APIRouter(application)),
            ],
        )
        return application

    def run(self):
        """Start ioloop."""
        self._ioloop.start()
        self._ioloop.close()

    def stop(self):
        """Stop ioloop."""
        LOGGER.debug("Stopping webserver")
        self._ioloop.stop()
