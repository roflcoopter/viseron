"""Discord webhook notifications."""

from __future__ import annotations

import asyncio
import logging
import os
from threading import Lock, Thread
from typing import TYPE_CHECKING

import requests
import voluptuous as vol

from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import EVENT_RECORDER_COMPLETE, EVENT_RECORDER_START
from viseron.domains.camera.recorder import EventRecorderData, Recording
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict

from .const import (
    COMPONENT,
    CONFIG_CAMERAS,
    CONFIG_DETECTION_LABEL,
    CONFIG_DETECTION_LABEL_DEFAULT,
    CONFIG_DISCORD_WEBHOOK_URL,
    CONFIG_MAX_VIDEO_SIZE_MB,
    CONFIG_MAX_VIDEO_SIZE_MB_DEFAULT,
    CONFIG_SEND_THUMBNAIL,
    CONFIG_SEND_VIDEO,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DETECTION_LABEL,
    DESC_DISCORD_WEBHOOK_URL,
    DESC_MAX_VIDEO_SIZE_MB,
    DESC_SEND_THUMBNAIL,
    DESC_SEND_VIDEO,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron

LOGGER = logging.getLogger(__name__)

CAMERA_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_DISCORD_WEBHOOK_URL,
            description=DESC_DISCORD_WEBHOOK_URL,
        ): str,
        vol.Optional(
            CONFIG_DETECTION_LABEL,
            description=DESC_DETECTION_LABEL,
        ): str,
        vol.Optional(
            CONFIG_SEND_THUMBNAIL,
            description=DESC_SEND_THUMBNAIL,
        ): bool,
        vol.Optional(
            CONFIG_SEND_VIDEO,
            description=DESC_SEND_VIDEO,
        ): bool,
        vol.Optional(
            CONFIG_MAX_VIDEO_SIZE_MB,
            description=DESC_MAX_VIDEO_SIZE_MB,
        ): int,
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): {
            vol.Required(
                CONFIG_DISCORD_WEBHOOK_URL, description=DESC_DISCORD_WEBHOOK_URL
            ): str,
            vol.Optional(
                CONFIG_DETECTION_LABEL,
                description=DESC_DETECTION_LABEL,
                default=CONFIG_DETECTION_LABEL_DEFAULT,
            ): str,
            vol.Optional(
                CONFIG_SEND_THUMBNAIL, description=DESC_SEND_THUMBNAIL, default=True
            ): bool,
            vol.Optional(
                CONFIG_SEND_VIDEO, description=DESC_SEND_VIDEO, default=True
            ): bool,
            vol.Optional(
                CONFIG_MAX_VIDEO_SIZE_MB,
                description=DESC_MAX_VIDEO_SIZE_MB,
                default=CONFIG_MAX_VIDEO_SIZE_MB_DEFAULT,
            ): int,
            vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
                CameraIdentifier(): vol.All(CoerceNoneToDict(), CAMERA_SCHEMA),
            },
        }
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config) -> bool:
    """Set up the Discord component."""
    component_config = config[COMPONENT]

    discord_notifier = DiscordNotifier(vis, component_config)
    Thread(target=discord_notifier.run_async).start()

    vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, discord_notifier.stop)
    return True


class DiscordNotifier:
    """
    Discord webhook notifier class.

    This class sends notifications to a Discord webhook when an event occurs.
    """

    def __init__(self, vis, config) -> None:
        self._vis = vis
        self._config = config
        self._webhook_url = self._config[CONFIG_DISCORD_WEBHOOK_URL]
        self._loop = asyncio.new_event_loop()
        self._stop_event = asyncio.Event()
        self._active_recordings: dict[int, Recording] = {}
        self._sent_recordings: set[int] = set()
        self._lock = Lock()

        # Register for recorder events for all configured cameras
        for camera_identifier in self._config[CONFIG_CAMERAS]:
            self._vis.listen_event(
                EVENT_RECORDER_START.format(camera_identifier=camera_identifier),
                self._recorder_start_event,
            )
            self._vis.listen_event(
                EVENT_RECORDER_COMPLETE.format(camera_identifier=camera_identifier),
                self._recorder_complete_event,
            )

        self._vis.data[COMPONENT] = self

    def _get_camera_config(self, camera_identifier: str, key: str, default=None):
        """Get camera-specific config or global default."""
        camera_config = self._config[CONFIG_CAMERAS].get(camera_identifier, {})
        return camera_config.get(key, self._config.get(key, default))

    def _get_webhook_url(self, camera_identifier: str | None):
        """Get webhook URL for a specific camera or global default."""
        camera_config = self._config[CONFIG_CAMERAS].get(camera_identifier, {})
        return camera_config.get(CONFIG_DISCORD_WEBHOOK_URL, self._webhook_url)

    def _recorder_start_event(self, event_data: Event[EventRecorderData]) -> None:
        """Handle recorder start event."""
        camera = event_data.data.camera
        recording = event_data.data.recording

        # Always send a start notification with message
        message = f"Recording started on {camera.identifier}"
        if recording.objects:
            message += f" - Detected {recording.objects[0].label}"

        # Check if thumbnail should be included
        send_thumbnail = self._get_camera_config(
            camera.identifier, CONFIG_SEND_THUMBNAIL, True
        )
        thumbnail_path = recording.thumbnail_path

        if (
            send_thumbnail
            and thumbnail_path is not None
            and os.path.exists(thumbnail_path)
        ):
            # Send message with thumbnail
            self._send_discord_file(
                thumbnail_path, message, "thumbnail.jpg", camera.identifier
            )
        else:
            # Send message only
            self._send_discord_message(message, camera.identifier)

    def _recorder_complete_event(self, event_data: Event[EventRecorderData]) -> None:
        """Handle recorder complete event."""
        asyncio.run_coroutine_threadsafe(
            self._send_notifications(event_data), self._loop
        )

    async def _send_notifications(self, event_data: Event[EventRecorderData]) -> None:
        """Send notifications to Discord webhook."""
        camera: AbstractCamera = event_data.data.camera
        recording = event_data.data.recording

        # Check if this recording has already been sent
        with self._lock:
            already_sent = recording.id in self._sent_recordings

        # Check if video sending is enabled for this camera
        send_video = self._get_camera_config(camera.identifier, CONFIG_SEND_VIDEO, True)

        # Get max video size for this camera
        max_size_mb = self._get_camera_config(
            camera.identifier,
            CONFIG_MAX_VIDEO_SIZE_MB,
            CONFIG_MAX_VIDEO_SIZE_MB_DEFAULT,
        )
        max_size_bytes = max_size_mb * 1024 * 1024

        # Prepare message
        message = f"Recording completed for {camera.identifier}"
        if recording.objects:
            message += f" - Detected {recording.objects[0].label}"

        # Check if we can send video
        clip_path = recording.clip_path
        can_send_video = (
            not already_sent
            and send_video
            and clip_path is not None
            and os.path.exists(clip_path)
        )

        # If we can't send video, send a message with thumbnail
        if not can_send_video:
            # Send message
            self._send_discord_message(message, camera.identifier)

            # Send thumbnail if configured and available
            send_thumbnail = self._get_camera_config(
                camera.identifier, CONFIG_SEND_THUMBNAIL, True
            )
            thumbnail_path = recording.thumbnail_path
            if (
                send_thumbnail
                and thumbnail_path is not None
                and os.path.exists(thumbnail_path)
            ):
                self._send_discord_file(
                    thumbnail_path,
                    f"Thumbnail for {camera.identifier}",
                    "thumbnail.jpg",
                    camera.identifier,
                )
        else:
            # We can send video, check file size
            assert clip_path is not None  # For type checking
            file_size = os.path.getsize(clip_path)

            # Prepare caption for video
            caption = f"Complete video from {camera.identifier}"
            if recording.objects:
                caption += f" - Detected {recording.objects[0].label}"

            # If file is smaller than the limit, send the complete video
            if file_size <= max_size_bytes:
                LOGGER.info(
                    f"Sending complete video file ({file_size / 1024 / 1024:.1f}MB)."
                )
                self._send_discord_file(
                    clip_path,
                    caption,
                    f"{camera.identifier}_event_complete.mp4",
                    camera.identifier,
                )
            else:
                # Video is too large, send the first max_size_bytes
                LOGGER.info(
                    f"Video too large ({file_size / 1024 / 1024:.1f}MB), "
                    f"sending first {max_size_mb}MB."
                )
                # Calculate approximate percentage of the video that is being sent
                percentage = min(100, int((max_size_bytes / file_size) * 100))
                self._send_discord_file_partial(
                    clip_path,
                    f"{caption} \r\n"
                    f"Truncated to {max_size_mb}MB / {percentage}% of the original "
                    f"video due to Discord file size limit.\r\n"
                    f"Note: The video player may show the full duration, "
                    f"but playback will stop early due to truncation.",
                    f"{camera.identifier}_event_partial.mp4",
                    max_size_bytes,
                    camera.identifier,
                )

    def _send_discord_message(self, content: str, camera_identifier: str) -> bool:
        """Send a text message to Discord webhook."""
        webhook_url = (
            self._get_webhook_url(camera_identifier)
            if camera_identifier
            else self._webhook_url
        )
        try:
            response = requests.post(webhook_url, json={"content": content}, timeout=30)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            LOGGER.error(f"Failed to send Discord message: {e}")
            return False

    def _send_discord_file(
        self, file_path: str, content: str, filename: str, camera_identifier: str
    ) -> bool:
        """Send a file to Discord webhook."""
        webhook_url = (
            self._get_webhook_url(camera_identifier)
            if camera_identifier
            else self._webhook_url
        )
        try:
            with open(file_path, "rb") as file:
                response = requests.post(
                    webhook_url,
                    files={"file": (filename, file)},
                    data={"content": content},
                    timeout=60,
                )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            LOGGER.error(f"Failed to send Discord file {file_path}: {e}")
            return False

    def _send_discord_file_partial(
        self,
        file_path: str,
        content: str,
        filename: str,
        max_bytes: int,
        camera_identifier: str,
    ) -> bool:
        """Send a partial file to Discord webhook (first max_bytes only)."""
        webhook_url = (
            self._get_webhook_url(camera_identifier)
            if camera_identifier
            else self._webhook_url
        )
        try:
            with open(file_path, "rb") as file:
                file_data = file.read(max_bytes)

            response = requests.post(
                webhook_url,
                files={"file": (filename, file_data)},
                data={"content": content},
                timeout=60,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            LOGGER.error(f"Failed to send partial Discord file {file_path}: {e}")
            return False

    async def _run_until_stopped(self):
        """Run until stopped."""
        while not self._stop_event.is_set():
            await asyncio.sleep(1)

    def run_async(self):
        """Run DiscordNotifier in a new event loop."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_until_stopped())
        LOGGER.info("DiscordNotifier done")

    def stop(self) -> None:
        """Stop DiscordNotifier component."""
        self._stop_event.set()
        LOGGER.info("Stopping DiscordNotifier")
