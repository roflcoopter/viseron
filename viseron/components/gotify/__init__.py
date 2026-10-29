"""Gotify notifications for Viseron."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import uuid
from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

import cv2
import requests

from viseron.components.webserver.const import (
    COMPONENT as WEBSERVER_COMPONENT,
    PUBLIC_IMAGE_TOKENS,
    PUBLIC_IMAGES_PATH,
)
from viseron.components.webserver.public_image_token import PublicImageToken
from viseron.const import DEFAULT_PORT, VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import EVENT_RECORDER_START
from viseron.helpers import escape_string, utcnow
from viseron.helpers.logs import (
    SensitiveInformationFilterTracker,
)
from viseron.watchdog.thread_watchdog import RestartableThread

from .config import GotifyConfig, GotifyRoot
from .const import COMPONENT

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera.recorder import EventRecorderData

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = GotifyRoot


def setup(vis: Viseron, config: GotifyRoot) -> bool:
    """Set up the Gotify component."""
    vis.data[COMPONENT] = GotifyEventNotifier(vis, config.gotify)

    return True


def unload(vis: Viseron) -> None:
    """Unload the Gotify component."""
    notifier = vis.data.get(COMPONENT)
    if notifier:
        notifier.stop()
        del vis.data[COMPONENT]


class GotifyEventNotifier:
    """Gotify event notifier class that sends notifications to a Gotify server."""

    def __init__(self, vis: Viseron, config: GotifyConfig) -> None:
        self._vis = vis
        self._config = config
        self._sensitive_string_tracker = SensitiveInformationFilterTracker()
        token = config.gotify_token.get_secret_value()
        self._sensitive_string_tracker.add_sensitive_string(token)
        self._sensitive_string_tracker.add_sensitive_string(escape_string(token))
        self._gotify_url = config.gotify_url.rstrip("/")
        self._gotify_token = config.gotify_token
        self._priority = config.priority
        self._loop = asyncio.new_event_loop()
        self._stop_event = asyncio.Event()

        self._event_listeners = []
        for camera_identifier in config.cameras:
            # Listen for recording start events
            self._event_listeners.append(
                self._vis.listen_event(
                    EVENT_RECORDER_START.format(camera_identifier=camera_identifier),
                    self._recording_start_event_handler,
                )
            )

        self._thread = RestartableThread(
            name="GotifyNotifierThread", daemon=True, target=self.run_async
        )
        self._thread.start()
        self._event_listeners.append(
            vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)
        )

    def _recording_start_event_handler(
        self, event_data: Event[EventRecorderData]
    ) -> None:
        """Handle recording start events."""
        camera = event_data.data.camera
        recording = event_data.data.recording
        camera_identifier = camera.identifier

        # Keys that are not set for the camera fall back to the global config
        camera_config = self._config.cameras[camera_identifier]

        # Get detected objects from the recording
        objects = recording.objects

        if not objects:
            # Skip if no objects
            return

        # Check if we should filter by detection label
        detection_labels = (
            camera_config.detection_label
            if camera_config.detection_label is not None
            else self._config.detection_label
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
        send_thumbnail = (
            camera_config.send_thumbnail
            if camera_config.send_thumbnail is not None
            else self._config.send_thumbnail
        )

        # Send notification with image if thumbnail is enabled and available
        if send_thumbnail and thumbnail is not None:
            try:
                # Resize the thumbnail if needed
                height, width = thumbnail.shape[:2]
                max_size = self._config.image_max_size

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
                use_public_url = (
                    camera_config.use_public_url
                    if camera_config.use_public_url is not None
                    else self._config.use_public_url
                )

                # Send notification with image
                asyncio.run_coroutine_threadsafe(
                    self._send_notification_with_image(
                        title, message, resized_thumbnail, use_public_url
                    ),
                    self._loop,
                )
            except (cv2.error, TypeError, ValueError):
                LOGGER.exception("Failed to prepare image notification")
                # Fall back to text-only notification
                asyncio.run_coroutine_threadsafe(
                    self._send_text_notification(title, message), self._loop
                )
        # Send text-only notification if image is not enabled or not available
        else:
            asyncio.run_coroutine_threadsafe(
                self._send_text_notification(title, message), self._loop
            )

    async def _send_text_notification(self, title, message) -> None:
        """Send a text-only notification to Gotify."""
        try:
            self._send_gotify_message(title, message)
        except requests.RequestException:
            LOGGER.exception("Failed to send Gotify message")

    async def _send_notification_with_image(
        self, title, message, image, use_public_url=False
    ) -> None:
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
        except requests.RequestException:
            LOGGER.exception("Failed to send Gotify message with image")
            # Fall back to text-only notification
            await self._send_text_notification(title, message)

    def _send_gotify_message(self, title, message) -> None:
        """Send a simple text message to Gotify."""
        url = f"{self._gotify_url}/message"
        headers = {"X-Gotify-Key": self._gotify_token.get_secret_value()}
        data = {
            "title": title,
            "message": message,
            "priority": self._priority,
        }

        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code != HTTPStatus.OK:
            LOGGER.error(
                "Failed to send Gotify message: %s - %s",
                response.status_code,
                response.text,
            )
        else:
            pass

    def _send_gotify_message_with_image(self, title, message, image) -> None:
        """Send a message with an image attachment to Gotify."""
        if image is None:
            LOGGER.error("Cannot send image notification: image is None")
            return

        url = f"{self._gotify_url}/message"
        headers = {"X-Gotify-Key": self._gotify_token.get_secret_value()}

        # Encode the image as base64 with configured quality
        quality = self._config.image_quality
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
        if response.status_code != HTTPStatus.OK:
            LOGGER.error(
                "Failed to send Gotify message with image: %s - %s",
                response.status_code,
                response.text,
            )
        else:
            pass

    def _send_gotify_message_with_public_url(self, title, message, image) -> None:
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
            quality = self._config.image_quality
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
            headers = {"X-Gotify-Key": self._gotify_token.get_secret_value()}
            data = {
                "title": title,
                "message": message_with_image,
                "priority": self._priority,
                "extras": {"client::display": {"contentType": "text/markdown"}},
            }

            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code != HTTPStatus.OK:
                LOGGER.error(
                    "Failed to send Gotify message with public URL: %s - %s",
                    response.status_code,
                    response.text,
                )
                # Clean up image file and token if message failed
                if os.path.exists(image_file):
                    os.remove(image_file)
                del self._vis.data[PUBLIC_IMAGE_TOKENS][token]
        except Exception:
            LOGGER.exception("Failed to create public URL for image")
            # Clean up on error
            if os.path.exists(image_file):
                os.remove(image_file)
            if token in self._vis.data[PUBLIC_IMAGE_TOKENS]:
                del self._vis.data[PUBLIC_IMAGE_TOKENS][token]
            raise

    async def _run_until_stopped(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(1)

    def run_async(self) -> None:
        """Run GotifyEventNotifier in a new event loop."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_until_stopped())
        self._loop.close()

    def stop(self) -> None:
        """Stop GotifyEventNotifier component."""
        LOGGER.debug("Stopping GotifyEventNotifier")
        for unsubscribe in self._event_listeners:
            unsubscribe()
        self._event_listeners.clear()
        self._stop_event.set()
        self._thread.stop()
        self._thread.join(timeout=5)
        self._sensitive_string_tracker.clear_sensitive_strings()
        LOGGER.debug("GotifyEventNotifier stopped")
