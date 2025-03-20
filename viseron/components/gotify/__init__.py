"""Gotify notifications for Viseron."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import TYPE_CHECKING

import cv2
import requests
import voluptuous as vol

from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import EVENT_RECORDER_START
from viseron.domains.camera.recorder import EventRecorderData
from viseron.helpers import escape_string
from viseron.helpers.logs import SensitiveInformationFilter
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    COMPONENT,
    CONFIG_CAMERAS,
    CONFIG_DETECTION_LABEL,
    CONFIG_DETECTION_LABEL_DEFAULT,
    CONFIG_GOTIFY_PRIORITY,
    CONFIG_GOTIFY_PRIORITY_DEFAULT,
    CONFIG_GOTIFY_TOKEN,
    CONFIG_GOTIFY_URL,
    CONFIG_SEND_THUMBNAIL,
    DESC_CAMERA_DETECTION_LABEL,
    DESC_CAMERA_SEND_THUMBNAIL,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DETECTION_LABEL,
    DESC_GOTIFY_PRIORITY,
    DESC_GOTIFY_TOKEN,
    DESC_GOTIFY_URL,
    DESC_SEND_THUMBNAIL,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron

LOGGER = logging.getLogger(__name__)

CAMERA_SCHEMA = vol.Schema(
    {
        vol.Optional(
            "detection_label",
            description=DESC_CAMERA_DETECTION_LABEL,
        ): str,
        vol.Optional(
            "send_thumbnail",
            description=DESC_CAMERA_SEND_THUMBNAIL,
        ): bool,
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): {
            vol.Required(CONFIG_GOTIFY_URL, description=DESC_GOTIFY_URL): str,
            vol.Required(CONFIG_GOTIFY_TOKEN, description=DESC_GOTIFY_TOKEN): str,
            vol.Optional(
                CONFIG_GOTIFY_PRIORITY,
                description=DESC_GOTIFY_PRIORITY,
                default=CONFIG_GOTIFY_PRIORITY_DEFAULT,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
            vol.Optional(
                CONFIG_DETECTION_LABEL,
                description=DESC_DETECTION_LABEL,
                default=CONFIG_DETECTION_LABEL_DEFAULT,
            ): str,
            vol.Optional(
                CONFIG_SEND_THUMBNAIL, description=DESC_SEND_THUMBNAIL, default=False
            ): bool,
            vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
                CameraIdentifier(): vol.All(CoerceNoneToDict(), CAMERA_SCHEMA)
            },
        }
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config) -> bool:
    """Set up the Gotify component."""
    component_config = config[COMPONENT]

    gotify_notifier = GotifyEventNotifier(vis, component_config)
    RestartableThread(
        target=gotify_notifier.run_async, name="gotify_event_notifier"
    ).start()

    vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, gotify_notifier.stop)
    return True


class GotifyEventNotifier:
    """Gotify event notifier class that sends notifications to a Gotify server."""

    def __init__(self, vis, config) -> None:
        self._vis = vis
        self._config = config
        SensitiveInformationFilter.add_sensitive_string(
            self._config[CONFIG_GOTIFY_TOKEN]
        )
        SensitiveInformationFilter.add_sensitive_string(
            escape_string(self._config[CONFIG_GOTIFY_TOKEN])
        )
        self._gotify_url = self._config[CONFIG_GOTIFY_URL].rstrip("/")
        self._gotify_token = self._config[CONFIG_GOTIFY_TOKEN]
        self._priority = self._config[CONFIG_GOTIFY_PRIORITY]
        self._loop = asyncio.new_event_loop()
        self._stop_event = asyncio.Event()

        for camera_identifier in self._config[CONFIG_CAMERAS]:
            # Listen for recording start events
            self._vis.listen_event(
                EVENT_RECORDER_START.format(camera_identifier=camera_identifier),
                self._recording_start_event_handler,
            )
        vis.data[COMPONENT] = self

    def _recording_start_event_handler(
        self, event_data: Event[EventRecorderData]
    ) -> None:
        """Handle recording start events."""
        camera = event_data.data.camera
        recording = event_data.data.recording
        camera_identifier = camera.identifier

        # Get camera-specific configuration or fall back to global configuration
        camera_config = self._config[CONFIG_CAMERAS].get(camera_identifier, {})

        # Get detected objects from the recording
        objects = recording.objects

        if not objects:
            # Skip if no objects
            return

        # Check if we should filter by detection label
        # First check camera setting, then fall back to global setting, then to default
        camera_detection_label = camera_config.get("detection_label")
        global_detection_label = self._config.get(
            CONFIG_DETECTION_LABEL, CONFIG_DETECTION_LABEL_DEFAULT
        )
        detection_labels = (
            camera_detection_label
            if camera_detection_label is not None
            else global_detection_label
        )

        # Find matching objects
        matching_object = None
        if detection_labels:
            # Support comma-separated list of labels
            allowed_labels = [label.strip() for label in detection_labels.split(",")]

            # Check if any object has a label that matches the allowed labels
            for obj in objects:
                if obj.label in allowed_labels:
                    matching_object = obj
                    break

            if not matching_object:
                # Skip if no object with allowed label was found
                return
        else:
            # If no detection labels are specified, use the first object
            matching_object = objects[0]

        # Create notification message
        title = f"{camera_identifier} recording started: {matching_object.label}"
        message = f"Recording started for {matching_object.label}"

        # Get the thumbnail from the recording
        thumbnail = recording.thumbnail

        # Check if thumbnail is enabled for this camera
        # First check camera-specific setting, then fall back to global setting
        camera_send_thumbnail = camera_config.get("send_thumbnail")
        global_send_thumbnail = self._config.get(CONFIG_SEND_THUMBNAIL, False)
        send_thumbnail = (
            camera_send_thumbnail
            if camera_send_thumbnail is not None
            else global_send_thumbnail
        )

        # Send notification with image if thumbnail is enabled and available
        if send_thumbnail and thumbnail is not None:
            try:
                # Resize the thumbnail if needed
                height, width = thumbnail.shape[:2]
                max_size = 800
                if width > height:
                    new_width = min(width, max_size)
                    new_height = int((new_width / width) * height)
                else:
                    new_height = min(height, max_size)
                    new_width = int((new_height / height) * width)

                resized_thumbnail = cv2.resize(
                    thumbnail, (new_width, new_height), interpolation=cv2.INTER_AREA
                )

                # Send notification with image
                asyncio.run_coroutine_threadsafe(
                    self._send_notification_with_image(
                        title, message, resized_thumbnail
                    ),
                    self._loop,
                )
            except (cv2.error, TypeError, ValueError) as exc:
                LOGGER.error("Failed to prepare image notification: %s", exc)
                # Fall back to text-only notification
                asyncio.run_coroutine_threadsafe(
                    self._send_text_notification(title, message), self._loop
                )
        # Send text-only notification if image is not enabled or not available
        else:
            asyncio.run_coroutine_threadsafe(
                self._send_text_notification(title, message), self._loop
            )

    async def _send_text_notification(self, title, message):
        """Send a text-only notification to Gotify."""
        try:
            self._send_gotify_message(title, message)
        except requests.RequestException as exc:
            LOGGER.error("Failed to send Gotify message: %s", exc)

    async def _send_notification_with_image(self, title, message, image):
        """Send a notification with image to Gotify."""
        if image is None:
            LOGGER.error("Cannot send image notification: image is None")
            # Fall back to text-only notification
            await self._send_text_notification(title, message)
            return

        try:
            self._send_gotify_message_with_image(title, message, image)
        except requests.RequestException as exc:
            LOGGER.error("Failed to send Gotify message with image: %s", exc)
            # Fall back to text-only notification
            await self._send_text_notification(title, message)

    def _send_gotify_message(self, title, message):
        """Send a simple text message to Gotify."""
        url = f"{self._gotify_url}/message"
        headers = {"X-Gotify-Key": self._gotify_token}
        data = {
            "title": title,
            "message": message,
            "priority": self._priority,
        }

        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code != 200:
            LOGGER.error(
                "Failed to send Gotify message: %s - %s",
                response.status_code,
                response.text,
            )
        else:
            pass

    def _send_gotify_message_with_image(self, title, message, image):
        """Send a message with an image attachment to Gotify."""
        if image is None:
            LOGGER.error("Cannot send image notification: image is None")
            return

        url = f"{self._gotify_url}/message"
        headers = {"X-Gotify-Key": self._gotify_token}

        # Encode the image as base64
        _, buffer = cv2.imencode(".jpg", image)
        image_base64 = base64.b64encode(buffer.tobytes()).decode("utf-8")

        # Include the image directly in the message using markdown
        # Format: data:image/jpeg;base64,<base64-encoded-image>
        image_markdown = f"![Image](data:image/jpeg;base64,{image_base64})"

        # Combine the text message with the image markdown
        message_with_image = f"{message}\n\n{image_markdown}"

        # Create the message with the image embedded in markdown
        data = {
            "title": title,
            "message": message_with_image,
            "priority": self._priority,
            "extras": {"client::display": {"contentType": "text/markdown"}},
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code != 200:
            LOGGER.error(
                "Failed to send Gotify message with image: %s - %s",
                response.status_code,
                response.text,
            )
        else:
            pass

    async def _run_until_stopped(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(1)

    def run_async(self):
        """Run GotifyEventNotifier in a new event loop."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_until_stopped())

    def stop(self) -> None:
        """Stop GotifyEventNotifier component."""
        self._stop_event.set()
