"""Gotify notifications for Viseron."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

import cv2
import requests
import voluptuous as vol

from viseron.components.webserver.const import (
    COMPONENT as WEBSERVER_COMPONENT,
    PUBLIC_IMAGE_TOKENS,
    PUBLIC_IMAGES_PATH,
)
from viseron.components.webserver.public_image_token import PublicImageToken
from viseron.const import DEFAULT_PORT, VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import EVENT_RECORDER_START
from viseron.domains.camera.recorder import EventRecorderData
from viseron.helpers import escape_string, utcnow
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
    CONFIG_IMAGE_MAX_SIZE,
    CONFIG_IMAGE_MAX_SIZE_DEFAULT,
    CONFIG_IMAGE_QUALITY,
    CONFIG_IMAGE_QUALITY_DEFAULT,
    CONFIG_SEND_THUMBNAIL,
    CONFIG_USE_PUBLIC_URL,
    DESC_CAMERA_DETECTION_LABEL,
    DESC_CAMERA_SEND_THUMBNAIL,
    DESC_CAMERA_USE_PUBLIC_URL,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DETECTION_LABEL,
    DESC_GOTIFY_PRIORITY,
    DESC_GOTIFY_TOKEN,
    DESC_GOTIFY_URL,
    DESC_IMAGE_MAX_SIZE,
    DESC_IMAGE_QUALITY,
    DESC_SEND_THUMBNAIL,
    DESC_USE_PUBLIC_URL,
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
        vol.Optional(
            "use_public_url",
            description=DESC_CAMERA_USE_PUBLIC_URL,
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
            vol.Optional(
                CONFIG_USE_PUBLIC_URL, description=DESC_USE_PUBLIC_URL, default=False
            ): bool,
            vol.Optional(
                CONFIG_IMAGE_MAX_SIZE,
                description=DESC_IMAGE_MAX_SIZE,
                default=CONFIG_IMAGE_MAX_SIZE_DEFAULT,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=7680)),
            vol.Optional(
                CONFIG_IMAGE_QUALITY,
                description=DESC_IMAGE_QUALITY,
                default=CONFIG_IMAGE_QUALITY_DEFAULT,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
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
                max_size = self._config.get(
                    CONFIG_IMAGE_MAX_SIZE, CONFIG_IMAGE_MAX_SIZE_DEFAULT
                )

                # Skip resizing if max_size is 0 (use original size)
                if max_size == 0:
                    resized_thumbnail = thumbnail
                else:
                    if width > height:
                        new_width = min(width, max_size)
                        new_height = int((new_width / width) * height)
                    else:
                        new_height = min(height, max_size)
                        new_width = int((new_height / height) * width)

                    resized_thumbnail = cv2.resize(
                        thumbnail, (new_width, new_height), interpolation=cv2.INTER_AREA
                    )

                # Check if we should use public URL
                camera_use_public_url = camera_config.get("use_public_url")
                global_use_public_url = self._config.get(CONFIG_USE_PUBLIC_URL, False)
                use_public_url = (
                    camera_use_public_url
                    if camera_use_public_url is not None
                    else global_use_public_url
                )

                # Send notification with image
                asyncio.run_coroutine_threadsafe(
                    self._send_notification_with_image(
                        title, message, resized_thumbnail, use_public_url
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

    async def _send_notification_with_image(
        self, title, message, image, use_public_url=False
    ):
        """Send a notification with image to Gotify."""
        if image is None:
            LOGGER.error("Cannot send image notification: image is None")
            # Fall back to text-only notification
            await self._send_text_notification(title, message)
            return

        try:
            if use_public_url:
                self._send_gotify_message_with_public_url(title, message, image)
            else:
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

        # Encode the image as base64 with configured quality
        quality = self._config.get(CONFIG_IMAGE_QUALITY, CONFIG_IMAGE_QUALITY_DEFAULT)
        _, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
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

    def _send_gotify_message_with_public_url(self, title, message, image):
        """Send a message with a public URL to the image."""
        if image is None:
            LOGGER.error("Cannot send image notification: image is None")
            return

        # Save image to persistent directory
        token = str(uuid.uuid4())
        image_file = os.path.join(PUBLIC_IMAGES_PATH, f"{token}.jpg")

        try:
            # Get webserver component for configuration
            webserver = self._vis.data.get(WEBSERVER_COMPONENT)

            # Save the image with configured quality
            quality = self._config.get(
                CONFIG_IMAGE_QUALITY, CONFIG_IMAGE_QUALITY_DEFAULT
            )
            cv2.imwrite(image_file, image, [cv2.IMWRITE_JPEG_QUALITY, quality])

            # Get expiry hours and max downloads from webserver config
            expiry_hours = webserver.public_url_expiry_hours if webserver else 24
            max_downloads = webserver.public_url_max_downloads if webserver else 0

            # Create public image token
            expires_at = utcnow() + timedelta(hours=expiry_hours)
            public_image_token = PublicImageToken(
                file_path=image_file,
                token=token,
                expires_at=expires_at,
                remaining_downloads=max_downloads,
            )

            # Store the token
            self._vis.data[PUBLIC_IMAGE_TOKENS][token] = public_image_token

            # Generate public URL using webserver's public_base_url
            base_url = webserver.public_base_url if webserver else None

            if base_url:
                # Remove trailing slash if present
                base_url = base_url.rstrip("/")
                public_url = f"{base_url}/api/v1/publicimage?token={token}"
            else:
                # Fall back to localhost with default port
                public_url = (
                    f"http://localhost:{DEFAULT_PORT}/api/v1/publicimage?token={token}"
                )
                LOGGER.warning(
                    "Webserver public_base_url not configured, using localhost. "
                    "Images will only be accessible locally. "
                    "Configure it in webserver.public_base_url"
                )

            LOGGER.debug(f"Created public image URL: {public_url}")

            # Create markdown with image URL
            image_markdown = f"![Image]({public_url})"
            message_with_image = f"{message}\n\n{image_markdown}"

            # Send message with public URL
            url = f"{self._gotify_url}/message"
            headers = {"X-Gotify-Key": self._gotify_token}
            data = {
                "title": title,
                "message": message_with_image,
                "priority": self._priority,
                "extras": {"client::display": {"contentType": "text/markdown"}},
            }

            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code != 200:
                LOGGER.error(
                    "Failed to send Gotify message with public URL: %s - %s",
                    response.status_code,
                    response.text,
                )
                # Clean up image file and token if message failed
                if os.path.exists(image_file):
                    os.remove(image_file)
                del self._vis.data[PUBLIC_IMAGE_TOKENS][token]
        except Exception as exc:
            LOGGER.error("Failed to create public URL for image: %s", exc)
            # Clean up on error
            if os.path.exists(image_file):
                os.remove(image_file)
            if token in self._vis.data[PUBLIC_IMAGE_TOKENS]:
                del self._vis.data[PUBLIC_IMAGE_TOKENS][token]
            raise

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
