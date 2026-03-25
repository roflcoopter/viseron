"""Viseron webserver."""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
import threading
from typing import TYPE_CHECKING

import tornado.ioloop
import tornado.web
import voluptuous as vol
from tornado.routing import PathMatches

from viseron.components.webserver.auth import Auth
from viseron.const import DEFAULT_PORT, VISERON_SIGNAL_SHUTDOWN
from viseron.exceptions import ComponentNotReady
from viseron.helpers import current_system_datetime
from viseron.helpers.storage import Storage
from viseron.helpers.validators import CoerceNoneToDict, Deprecated

from .api import APIRouter
from .const import (
    COMPONENT,
    CONFIG_AUTH,
    CONFIG_DAYS,
    CONFIG_DEBUG,
    CONFIG_HOURS,
    CONFIG_MINUTES,
    CONFIG_PORT,
    CONFIG_PUBLIC_BASE_URL,
    CONFIG_PUBLIC_URL_EXPIRY_HOURS,
    CONFIG_PUBLIC_URL_MAX_DOWNLOADS,
    CONFIG_SESSION_EXPIRY,
    CONFIG_SUBPATH,
    DEFAULT_COMPONENT,
    DEFAULT_DEBUG,
    DEFAULT_PUBLIC_URL_EXPIRY_HOURS,
    DEFAULT_PUBLIC_URL_MAX_DOWNLOADS,
    DEFAULT_SESSION_EXPIRY,
    DEFAULT_SUBPATH,
    DESC_AUTH,
    DESC_COMPONENT,
    DESC_DAYS,
    DESC_DEBUG,
    DESC_HOURS,
    DESC_MINUTES,
    DESC_PORT,
    DESC_PUBLIC_BASE_URL,
    DESC_PUBLIC_URL_EXPIRY_HOURS,
    DESC_PUBLIC_URL_MAX_DOWNLOADS,
    DESC_SESSION_EXPIRY,
    DESC_SUBPATH,
    DOWNLOAD_TOKENS,
    PUBLIC_IMAGE_TOKENS,
    PUBLIC_IMAGES_PATH,
    WEBSERVER_STORAGE_KEY,
    WEBSOCKET_COMMANDS,
    WEBSOCKET_CONNECTIONS,
)
from .stream_handler import DynamicStreamHandler, StaticStreamHandler
from .websocket_api import WebSocketHandler
from .websocket_api.commands import (
    export_recording,
    export_snapshot,
    export_timespan,
    get_cameras,
    get_config,
    get_entities,
    handle_render_template,
    ping,
    restart_viseron,
    save_config,
    subscribe_event,
    subscribe_states,
    subscribe_timespans,
    unsubscribe_event,
    unsubscribe_states,
    unsubscribe_timespans,
)

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.webserver.download_token import DownloadToken
    from viseron.components.webserver.public_image_token import PublicImageToken


LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(
            COMPONENT, default=DEFAULT_COMPONENT, description=DESC_COMPONENT
        ): vol.All(
            CoerceNoneToDict(),
            {
                Deprecated(CONFIG_PORT, description=DESC_PORT): vol.All(
                    int, vol.Range(min=1024, max=49151)
                ),
                vol.Optional(
                    CONFIG_DEBUG, default=DEFAULT_DEBUG, description=DESC_DEBUG
                ): bool,
                vol.Optional(
                    CONFIG_SUBPATH, default=DEFAULT_SUBPATH, description=DESC_SUBPATH
                ): vol.Maybe(str),
                vol.Optional(
                    CONFIG_PUBLIC_BASE_URL,
                    description=DESC_PUBLIC_BASE_URL,
                ): str,
                vol.Optional(
                    CONFIG_PUBLIC_URL_EXPIRY_HOURS,
                    description=DESC_PUBLIC_URL_EXPIRY_HOURS,
                    default=DEFAULT_PUBLIC_URL_EXPIRY_HOURS,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=744)),
                vol.Optional(
                    CONFIG_PUBLIC_URL_MAX_DOWNLOADS,
                    description=DESC_PUBLIC_URL_MAX_DOWNLOADS,
                    default=DEFAULT_PUBLIC_URL_MAX_DOWNLOADS,
                ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Optional(CONFIG_AUTH, description=DESC_AUTH): vol.All(
                    CoerceNoneToDict(),
                    {
                        vol.Optional(
                            CONFIG_SESSION_EXPIRY,
                            default=DEFAULT_SESSION_EXPIRY,
                            description=DESC_SESSION_EXPIRY,
                        ): vol.All(
                            CoerceNoneToDict(),
                            {
                                vol.Optional(
                                    CONFIG_DAYS,
                                    description=DESC_DAYS,
                                ): vol.All(int, vol.Range(min=0)),
                                vol.Optional(
                                    CONFIG_HOURS,
                                    description=DESC_HOURS,
                                ): vol.All(int, vol.Range(min=0)),
                                vol.Optional(
                                    CONFIG_MINUTES,
                                    description=DESC_MINUTES,
                                ): vol.All(int, vol.Range(min=0)),
                            },
                        )
                    },
                ),
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config) -> bool:
    """Set up the webserver component."""
    config = config[COMPONENT]
    webserver = Webserver(vis, config)
    vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, webserver.stop)

    webserver.register_websocket_command(ping)
    webserver.register_websocket_command(subscribe_event)
    webserver.register_websocket_command(unsubscribe_event)
    webserver.register_websocket_command(subscribe_states)
    webserver.register_websocket_command(unsubscribe_states)
    webserver.register_websocket_command(get_cameras)
    webserver.register_websocket_command(get_config)
    webserver.register_websocket_command(save_config)
    webserver.register_websocket_command(restart_viseron)
    webserver.register_websocket_command(get_entities)
    webserver.register_websocket_command(subscribe_timespans)
    webserver.register_websocket_command(unsubscribe_timespans)
    webserver.register_websocket_command(export_recording)
    webserver.register_websocket_command(export_snapshot)
    webserver.register_websocket_command(export_timespan)
    webserver.register_websocket_command(handle_render_template)

    webserver.start()

    return True


class WebserverStore:
    """Webserver storage."""

    def __init__(self, vis: Viseron) -> None:
        self._store = Storage(vis, WEBSERVER_STORAGE_KEY)
        self._data = self._store.load()

    @property
    def cookie_secret(self):
        """Return cookie secret."""
        if "cookie_secret" not in self._data:
            self._data["cookie_secret"] = secrets.token_hex(64)
            self._store.save(self._data)
        return self._data["cookie_secret"]


def create_application(
    vis: Viseron, config, cookie_secret, xsrf_cookies=True
) -> tornado.web.Application:
    """Return tornado web app."""
    application = tornado.web.Application(
        [
            (
                r"/(?P<camera>[A-Za-z0-9_]+)/mjpeg-stream$",
                DynamicStreamHandler,
                {"vis": vis},
            ),
            (
                (
                    r"/(?P<camera>[A-Za-z0-9_]+)/mjpeg-streams/"
                    r"(?P<mjpeg_stream>[A-Za-z0-9_\-]+)$"
                ),
                StaticStreamHandler,
                {"vis": vis},
            ),
            (
                (
                    r"/(?P<camera>[A-Za-z0-9_]+)/static-mjpeg-streams/"
                    r"(?P<mjpeg_stream>[A-Za-z0-9_\-]+)$"
                ),
                StaticStreamHandler,
                {"vis": vis},
            ),
            (r"/websocket$", WebSocketHandler, {"vis": vis}),
        ],
        debug=config[CONFIG_DEBUG],
        autoreload=False,
        cookie_secret=cookie_secret,
        xsrf_cookies=xsrf_cookies,
    )
    application.add_handlers(
        r".*",
        [
            (PathMatches(r"/api/.*"), APIRouter(vis, application)),
        ],
    )
    return application


class Webserver(threading.Thread):
    """Webserver."""

    def __init__(self, vis: Viseron, config) -> None:
        super().__init__(name="Tornado Webserver", daemon=True)
        self._vis = vis
        self._config = config
        self._auth = None
        if self._config.get(CONFIG_AUTH, False):
            self._auth = Auth(vis, config)
        self._store = WebserverStore(vis)
        self._subpath = self._normalize_subpath(config.get(CONFIG_SUBPATH))

        vis.data[COMPONENT] = self
        vis.data[WEBSOCKET_COMMANDS] = {}
        vis.data[WEBSOCKET_CONNECTIONS] = []
        vis.data[DOWNLOAD_TOKENS] = {}
        vis.data[PUBLIC_IMAGE_TOKENS] = {}

        # Create persistent directory for public images
        os.makedirs(PUBLIC_IMAGES_PATH, exist_ok=True)

        # Clean up expired public images on startup
        self._cleanup_expired_public_images()

        self._asyncio_ioloop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._asyncio_ioloop)
        if config[CONFIG_DEBUG]:
            self._asyncio_ioloop.set_debug(True)

        self._application = create_application(vis, config, self._store.cookie_secret)
        self._httpserver = None
        try:
            self._httpserver = self._application.listen(
                DEFAULT_PORT,
                xheaders=True,
            )
        except OSError as error:
            if "Address already in use" in str(error):
                raise ComponentNotReady from error
            raise error
        self._ioloop = tornado.ioloop.IOLoop.current()

        # Schedule periodic cleanup of expired public images (every hour)
        self._cleanup_task: asyncio.Task | None = None

    @staticmethod
    def _normalize_subpath(subpath: str | None) -> str:
        """Normalize subpath to ensure it starts with / and doesn't end with /."""
        if not subpath:
            return ""
        subpath = subpath.strip()
        if not subpath.startswith("/"):
            subpath = "/" + subpath
        if subpath.endswith("/"):
            subpath = subpath.rstrip("/")
        return subpath

    def _cleanup_expired_public_images(self):
        """Clean up expired public images (files older than max expiry)."""
        try:

            timestamp_limit = current_system_datetime().timestamp() - (
                self.public_url_expiry_hours * 3600
            )
            cleaned_count = 0

            # Scan all files in the public images directory
            if os.path.exists(PUBLIC_IMAGES_PATH):
                for filename in os.listdir(PUBLIC_IMAGES_PATH):
                    file_path = os.path.join(PUBLIC_IMAGES_PATH, filename)

                    # Only process files (not directories)
                    if not os.path.isfile(file_path):
                        continue

                    # Check file age
                    try:
                        file_mtime = os.path.getmtime(file_path)
                        # If file is older than max expiry, delete it
                        if file_mtime < timestamp_limit:
                            os.remove(file_path)
                            cleaned_count += 1
                            LOGGER.debug(f"Deleted expired public image: {file_path} ")
                    except OSError as e:
                        LOGGER.error(f"Failed to process file {file_path}: {e}")

            if cleaned_count > 0:
                LOGGER.info(
                    f"Cleaned up {cleaned_count} expired public image(s) on startup"
                )
        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error(f"Error during expired public images cleanup: {e}")

    async def _periodic_cleanup(self):
        """Run periodic cleanup of expired public images."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._asyncio_ioloop.run_in_executor(
                    None, self._cleanup_expired_public_images
                )
            except asyncio.CancelledError:
                break
            except Exception as e:  # pylint: disable=broad-except
                LOGGER.error(f"Error during public images cleanup: {e}")

    @property
    def auth(self):
        """Return auth."""
        return self._auth

    @property
    def application(self):
        """Return application."""
        return self._application

    @property
    def download_tokens(self) -> dict[str, DownloadToken]:
        """Return download tokens."""
        return self._vis.data[DOWNLOAD_TOKENS]

    @property
    def public_image_tokens(self) -> dict[str, PublicImageToken]:
        """Return public image tokens."""
        return self._vis.data[PUBLIC_IMAGE_TOKENS]

    @property
    def public_base_url(self) -> str | None:
        """Return public base URL."""
        return self._config.get(CONFIG_PUBLIC_BASE_URL)

    @property
    def public_url_expiry_hours(self) -> int:
        """Return public URL expiry hours."""
        return self._config.get(
            CONFIG_PUBLIC_URL_EXPIRY_HOURS, DEFAULT_PUBLIC_URL_EXPIRY_HOURS
        )

    @property
    def public_url_max_downloads(self) -> int:
        """Return public URL max downloads."""
        return self._config.get(
            CONFIG_PUBLIC_URL_MAX_DOWNLOADS, DEFAULT_PUBLIC_URL_MAX_DOWNLOADS
        )

    @property
    def configured_subpath(self) -> str:
        """Return configured subpath."""
        return self._subpath

    def register_websocket_command(self, handler) -> None:
        """Register a websocket command."""
        if handler.command in self._vis.data[WEBSOCKET_COMMANDS]:
            LOGGER.error(f"Command {handler.command} has already been registered")
            return

        self._vis.data[WEBSOCKET_COMMANDS][handler.command] = (handler, handler.schema)

    def run(self) -> None:
        """Start ioloop."""
        # Start periodic cleanup task
        self._cleanup_task = self._asyncio_ioloop.create_task(self._periodic_cleanup())

        self._ioloop.start()
        self._ioloop.close(True)
        LOGGER.debug("IOLoop closed")

    def stop(self) -> None:
        """Stop ioloop."""
        LOGGER.debug("Stopping webserver")
        if self._httpserver:
            LOGGER.debug("Stopping HTTPServer")
            self._httpserver.stop()

        shutdown_event = threading.Event()

        async def shutdown():
            # Cancel cleanup task
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()

            for connection in self._vis.data[WEBSOCKET_CONNECTIONS]:
                LOGGER.debug("Closing websocket connection, %s", connection)
                await connection.force_close()

            tasks = [
                t
                for t in asyncio.all_tasks(self._asyncio_ioloop)
                if t is not asyncio.current_task()
            ]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            LOGGER.debug("Stopping IOloop")
            self._asyncio_ioloop.stop()
            self._ioloop.stop()
            LOGGER.debug("IOloop stopped")
            shutdown_event.set()

        self._ioloop.add_callback(shutdown)
        self.join()
        shutdown_event.wait()
        LOGGER.debug("Webserver stopped")
