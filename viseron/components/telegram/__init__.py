"""Telegram component."""

from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from textwrap import dedent
from typing import TYPE_CHECKING

import cv2
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
)
from telegram.request import HTTPXRequest

from viseron.components.onvif.const import COMPONENT as ONVIF_COMPONENT
from viseron.components.storage.models import TriggerTypes
from viseron.components.telegram.ptz_control import TelegramPTZ
from viseron.components.telegram.utils import limit_user_access
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import (
    DOMAIN as CAMERA_DOMAIN,
    EVENT_RECORDER_COMPLETE,
)
from viseron.domains.camera.recorder import EventRecorderData, ManualRecording
from viseron.exceptions import ComponentNotReady, DomainNotRegisteredError
from viseron.helpers import escape_string
from viseron.helpers.logs import SensitiveInformationFilterTracker
from viseron.viseron_types import Domain
from viseron.watchdog.thread_watchdog import RestartableThread

from .config import TelegramCameraConfig, TelegramConfig, TelegramRoot
from .const import COMPONENT, DATA_NOTIFIER, DATA_PTZ, DEFAULT_DETECTION_LABELS

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = TelegramRoot


def setup(vis: Viseron, config: TelegramRoot) -> bool:
    """Set up the telegram component."""
    component_config = config.telegram
    vis.data[COMPONENT] = {}

    # The onvif key is not part of TelegramRoot, so it is read from the whole
    # config. On reload vis.config is updated after setup, so it does not show
    # onvif being added or removed in the same reload.
    onvif_configured = bool(vis.config.get(ONVIF_COMPONENT))
    if onvif_configured and not vis.data.get(ONVIF_COMPONENT):
        raise ComponentNotReady(f"ONVIF component '{ONVIF_COMPONENT}' not ready yet")

    telegram_notifier = TelegramEventNotifier(vis, component_config)

    telegram_ptz = None
    # Check if ONVIF component is loaded and ready
    if not onvif_configured:
        LOGGER.info("No ONVIF component. Won't start Telegram PTZ Controller.")
    else:
        telegram_ptz = TelegramPTZ(vis, component_config, telegram_notifier)

    vis.data[COMPONENT][DATA_NOTIFIER] = telegram_notifier
    vis.data[COMPONENT][DATA_PTZ] = telegram_ptz

    if telegram_ptz:
        telegram_ptz.start()
    telegram_notifier.start()

    return True


def unload(vis: Viseron) -> None:
    """Unload the telegram component."""
    component_data = vis.data.get(COMPONENT, {})
    notifier = component_data.get(DATA_NOTIFIER)
    if notifier:
        notifier.stop()

    ptz = component_data.get(DATA_PTZ)
    if ptz:
        ptz.stop()

    vis.data.pop(COMPONENT, None)


def rescale_image_cv2(image_path, max_size):
    """Rescale an image using OpenCV."""
    # Load the image
    img = cv2.imread(image_path)
    height, width = img.shape[:2]

    # Calculate the new dimensions
    if width > height:
        new_width = min(width, max_size)
        new_height = int((new_width / width) * height)
    else:
        new_height = min(height, max_size)
        new_width = int((new_height / height) * width)

    # Rescale the image
    resized_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

    # Save the resized image
    resized_image_path = "rescaled_thumbnail.jpg"
    cv2.imwrite(resized_image_path, resized_img)
    return resized_image_path


class TelegramEventNotifier:
    """Telegram event notifier class.

    This class sends notifications to a Telegram chat when an event occurs.
    """

    def __init__(self, vis: Viseron, config: TelegramConfig) -> None:
        request = HTTPXRequest(
            connect_timeout=60,
            read_timeout=60,
            write_timeout=60,
            pool_timeout=60,
        )

        self._vis = vis
        self._config = config
        self._sensitive_string_tracker = SensitiveInformationFilterTracker()
        bot_token = config.telegram_bot_token.get_secret_value()
        self._sensitive_string_tracker.add_sensitive_string(bot_token)
        self._sensitive_string_tracker.add_sensitive_string(escape_string(bot_token))
        self._chat_ids = config.telegram_chat_ids
        self._loop = asyncio.new_event_loop()
        self._bot = Bot(token=bot_token)
        self._app = Application.builder().request(request).token(bot_token).build()
        self._stop_event = asyncio.Event()
        self._active_camera_identifier: str = next(iter(config.cameras), "")
        self._event_listeners = []
        for camera_identifier in config.cameras:
            self._event_listeners.append(
                self._vis.listen_event(
                    EVENT_RECORDER_COMPLETE.format(camera_identifier=camera_identifier),
                    self._recorder_complete_event,
                )
            )
        self._event_listeners.append(
            vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)
        )
        self._thread = RestartableThread(
            name="TelegramEventNotifier", daemon=True, target=self.run_async
        )

    def start(self) -> None:
        """Start the TelegramEventNotifier."""
        self._thread.start()

    @property
    def app(self) -> Application:
        """Return the Telegram Application."""
        return self._app

    @property
    def active_camera_identifier(self) -> str:
        """Return the active camera identifier."""
        return self._active_camera_identifier

    def _recorder_complete_event(self, event_data: Event[EventRecorderData]) -> None:
        asyncio.run_coroutine_threadsafe(
            self._send_notifications(event_data), self._loop
        )

    def _get_effective_detection_labels(self, camera_identifier: str) -> list[str]:
        """Return the list of allowed detection labels for a camera."""
        camera_config = self._config.cameras.get(
            camera_identifier, TelegramCameraConfig()
        )
        # The deprecated keys are read from __dict__, as reading the attribute of a
        # deprecated field emits a DeprecationWarning

        # Camera-level deprecated key (comma-separated string)
        camera_label_str: str | None = camera_config.__dict__["detection_label"]
        if camera_label_str is not None:
            return [lbl.strip() for lbl in camera_label_str.split(",") if lbl.strip()]

        # Camera-level new key
        if camera_config.detection_labels:
            return camera_config.detection_labels

        # Global deprecated key (comma-separated string)
        global_label_str: str | None = self._config.__dict__["detection_label"]
        if global_label_str:
            return [lbl.strip() for lbl in global_label_str.split(",") if lbl.strip()]

        # Global new key
        if self._config.detection_labels:
            return self._config.detection_labels

        return DEFAULT_DETECTION_LABELS

    async def _send_notifications(self, event_data: Event[EventRecorderData]) -> None:
        LOGGER.debug(
            "Preparing to send Telegram notification for event from camera %s",
            event_data.data.camera.identifier,
        )
        camera_identifier = event_data.data.camera.identifier
        objects = event_data.data.recording.objects
        matching_object = None
        if objects:
            allowed_labels = self._get_effective_detection_labels(camera_identifier)
            LOGGER.debug(
                "Allowed labels for camera %s: %s",
                camera_identifier,
                allowed_labels,
            )
            matching_object = next(
                (obj for obj in objects if obj.label in allowed_labels), None
            )
            if matching_object is None:
                LOGGER.debug(
                    "No detected objects with allowed labels for event from camera %s. "
                    "Detected objects: %s",
                    camera_identifier,
                    [obj.label for obj in objects],
                )
                return
        else:
            LOGGER.debug(
                "No detected objects for event from camera %s", camera_identifier
            )

        file = event_data.data.recording.clip_path
        if file and os.path.exists(file) and self._config.send_detection_video:
            caption = f"{event_data.data.camera.identifier}"
            if matching_object is not None:
                caption += f" detected a {matching_object.label}"

            if event_data.data.recording.thumbnail_path and os.path.exists(
                event_data.data.recording.thumbnail_path
            ):
                thumb = rescale_image_cv2(
                    event_data.data.recording.thumbnail_path, max_size=320
                )
            else:
                thumb = None

            for chat_id in self._chat_ids:
                with open(file, "rb") as video_file:
                    await self._bot.send_video(
                        chat_id=chat_id,
                        thumbnail=thumb,  # is ignored by telegram for small videos
                        video=video_file,
                        caption=caption,
                    )
        if (
            event_data.data.recording.thumbnail_path
            and os.path.exists(event_data.data.recording.thumbnail_path)
            and self._config.send_detection_thumbnail
        ):
            for chat_id in self._chat_ids:
                await self._bot.send_photo(
                    chat_id=chat_id,
                    photo=open(event_data.data.recording.thumbnail_path, "rb"),
                    caption=f"Thumbnail for {event_data.data.camera.identifier}",
                )
        if self._config.send_detection_message:
            for chat_id in self._chat_ids:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=f"Event from {event_data.data.camera.identifier}",
                )

    async def _listen(self) -> None:
        """Start listening for commands from Telegram."""
        self._app.add_handler(CommandHandler("record", self._record))
        self._app.add_handler(CommandHandler("r", self._record))
        self._app.add_handler(CommandHandler("stop_recorder", self._stop_recorder))
        self._app.add_handler(CommandHandler("sr", self._stop_recorder))
        self._app.add_handler(CommandHandler("list", self._list_cams))
        self._app.add_handler(CommandHandler("li", self._list_cams))
        self._app.add_handler(CommandHandler("select", self._list_cams))
        self._app.add_handler(CommandHandler("which", self._which_cam))
        self._app.add_handler(CommandHandler("w", self._which_cam))
        self._app.add_handler(CommandHandler("toggle", self._toggle_camera))
        self._app.add_handler(CommandHandler("t", self._toggle_camera))
        self._app.add_handler(CommandHandler("snapshot", self._snapshot))
        self._app.add_handler(CommandHandler("help", self._help))
        self._app.add_handler(CallbackQueryHandler(self._callback_parser))

        try:
            await self._app.initialize()
            await self._app.start()
            if self._app.updater:
                await self._app.updater.start_polling()
            else:
                raise RuntimeError("Updater not found")

            while not self._stop_event.is_set():
                await asyncio.sleep(1)
        finally:
            if self._app.updater and self._app.updater.running:
                await self._app.updater.stop()

            if self._app.running:
                await self._app.stop()

            await self._app.shutdown()

    def run_async(self):
        """Run TelegramEventNotifier in a new event loop."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._listen())
        self._loop.close()
        LOGGER.info("TelegramEventNotifier done")

    def stop(self) -> None:
        """Stop TelegramEventNotifier component."""
        LOGGER.debug("Stopping Telegram Event Notifier")
        for unsubscribe in self._event_listeners:
            unsubscribe()
        self._event_listeners.clear()
        self._stop_event.set()
        self._thread.stop()
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            LOGGER.error("Telegram Event Notifier thread did not stop within timeout")
        self._sensitive_string_tracker.clear_sensitive_strings()
        LOGGER.debug("Telegram Event Notifier stopped")

    def get_camera(self, camera_identifier: str) -> AbstractCamera | None:
        """Get camera instance."""
        try:
            return self._vis.get_registered_domain(CAMERA_DOMAIN, camera_identifier)
        except DomainNotRegisteredError:
            return None

    def get_cameras(self) -> dict[str, AbstractCamera] | None:
        """Get all registered camera instances."""
        try:
            return self._vis.get_registered_identifiers(CAMERA_DOMAIN)
        except DomainNotRegisteredError:
            return None

    @limit_user_access
    async def _callback_parser(self, update: Update, _context: CallbackContext) -> None:
        """Parse the callback data from the inline keyboard."""
        query = update.callback_query
        if query:
            await query.answer(read_timeout=30)
            self._active_camera_identifier = str(query.data)
            await query.edit_message_text(text=f"Switched to camera {query.data}")

    @limit_user_access
    async def _list_cams(self, update: Update, _context: CallbackContext) -> None:
        """
        List all available cameras.

        The user can select a camera to switch to by clicking on the camera name.
        """
        try:
            keyboard = []
            cameras = self.get_cameras() or {}
            for cam in cameras.values():
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"{cam.name or cam.identifier}",
                            callback_data=f"{cam.identifier}",
                        )
                    ]
                )
            if update.message:
                if len(cameras) > 0:
                    await update.message.reply_text(
                        "Select a camera",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                    )
                else:
                    await update.message.reply_text("No cameras registered.")
        except TelegramError as e:
            LOGGER.error(e)

    @limit_user_access
    async def _which_cam(self, update: Update, _context: CallbackContext) -> None:
        """Get the currently active camera."""
        if update.message:
            if self.active_camera_identifier:
                await update.message.reply_text(
                    f"Active camera: <b>{self.active_camera_identifier}</b>",
                    parse_mode=ParseMode.HTML,
                )
            else:
                await update.message.reply_text("No camera selected.")

    @limit_user_access
    async def _snapshot(self, update: Update, _context: CallbackContext) -> None:
        """Take a snapshot with the camera."""
        cam: AbstractCamera | None = self.get_camera(self.active_camera_identifier)
        if cam:
            _ret, snapshot = cam.get_snapshot(cam.current_frame)
            if update.message and snapshot:
                await update.message.reply_photo(
                    photo=snapshot,
                    caption=f"Snapshot from <b>{cam.name or cam.identifier}</b>",
                    parse_mode=ParseMode.HTML,
                )
        else:
            if update.message:
                await update.message.reply_text("No active camera.")

    @limit_user_access
    async def _toggle_camera(self, update: Update, _context: CallbackContext) -> None:
        """Toggle the camera on or off."""
        cam: AbstractCamera | None = self.get_camera(self.active_camera_identifier)
        if cam:
            if cam.is_on:
                cam.stop_camera()
                if update.message:
                    await update.message.reply_text(
                        f"<b>{cam.name or cam.identifier}</b> is turned off.",
                        parse_mode=ParseMode.HTML,
                    )
            else:
                cam.start_camera()
                if update.message:
                    await update.message.reply_text(
                        f"<b>{cam.name or cam.identifier}</b> is turned on.",
                        parse_mode=ParseMode.HTML,
                    )

    @limit_user_access
    async def _record(self, update: Update, context: CallbackContext) -> None:
        """
        Record a video with the camera.

        @param duration: The duration of the recording in seconds

        Parameters are passed through the Telegram message e.g.:

        /record 60

        This will record a video for 60 seconds and return it.

        /record 60 5 will record five 60 second videos and return them.
        """
        duration: int | None = None
        number_of_videos = 1
        if context.args and len(context.args) > 0:
            duration = int(context.args[0])
        if context.args and len(context.args) > 1:
            number_of_videos = int(context.args[1])
        cam: AbstractCamera | None = self.get_camera(self.active_camera_identifier)
        if cam is None:
            if update.message:
                await update.message.reply_text("Camera not found.")
            return

        try:
            nvr = self._vis.get_registered_domain(Domain.NVR, cam.identifier)
        except DomainNotRegisteredError:
            if update.message:
                await update.message.reply_text("NVR component not enabled for camera.")
            return

        if (
            cam.is_recording
            and cam.recorder.active_recording
            and cam.recorder.active_recording.trigger_type == TriggerTypes.MANUAL
        ):
            if update.message:
                await update.message.reply_text("Camera is already recording.")
            return
        if cam.current_frame is None:
            if update.message:
                await update.message.reply_text("No frame available.")
            return

        manual_recording = ManualRecording(duration=duration)
        for _ in range(number_of_videos):
            nvr.start_manual_recording(
                manual_recording,
            )
            if update.message:
                await update.message.reply_text(
                    f"Started manual recording for camera <b>{cam.identifier}</b> with "
                    f"{f'duration {duration}s' if duration else 'no duration'}.",
                    parse_mode=ParseMode.HTML,
                )
            if duration:
                await asyncio.sleep(duration)

    @limit_user_access
    async def _stop_recorder(self, update: Update, _context: CallbackContext) -> None:
        """
        Stop an ongoing manual recording.

        Example usage:
        /stop_recorder
        This will stop the current manual recording.
        """
        cam: AbstractCamera | None = self.get_camera(self.active_camera_identifier)
        if cam is None:
            if update.message:
                await update.message.reply_text("Camera not found.")
            return

        try:
            nvr = self._vis.get_registered_domain(Domain.NVR, cam.identifier)
        except DomainNotRegisteredError:
            if update.message:
                await update.message.reply_text("NVR component not enabled for camera.")
            return

        if not (
            cam.is_recording
            and cam.recorder.active_recording
            and cam.recorder.active_recording.trigger_type == TriggerTypes.MANUAL
        ):
            if update.message:
                await update.message.reply_text("No ongoing manual recording to stop.")
            return
        nvr.stop_manual_recording()
        if update.message:
            await update.message.reply_text("Manual recording stopped.")

    @limit_user_access
    async def _help(self, update: Update, context: CallbackContext) -> None:
        """
        Display a list of commands and their description.

        @param command: The command to get help for.
        Examples:
        /help
        This will display a list of all available commands.
        /help left
        This will display the help text for the /left command.
        """
        if not update.message:
            return

        if not self._app:
            return

        handler_commands = defaultdict(list)
        handlers = list(self._app.handlers[0])

        for handler in handlers:
            if isinstance(handler, CommandHandler):
                command = list(handler.commands)[0]
                handler_commands[handler.callback].append(command)

        if context.args:
            command_arg = context.args[0].lstrip("/")
            for callback, cmds in handler_commands.items():
                if command_arg in cmds:
                    doc = callback.__doc__
                    if doc:
                        await update.message.reply_text(dedent(doc))
                    return

        commands = []
        for callback, cmds in handler_commands.items():
            doc = callback.__doc__
            if doc:
                command_list = " or ".join(f"/{cmd}" for cmd in cmds)
                first_line_doc = next(
                    (line.strip() for line in doc.split("\n") if line.strip()), ""
                )
                commands.append(f"{command_list} — {first_line_doc}")

        help_message = "Viseron Telegram commands:\n\n"
        help_message += "\n".join(commands)
        help_message += (
            "\n\nUse /help <command> to get more information about a command."
        )
        await update.message.reply_text(help_message)
