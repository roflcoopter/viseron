"""Telegram component."""

from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from textwrap import dedent
from threading import Thread
from typing import TYPE_CHECKING, Any

import cv2
import voluptuous as vol
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
)

from viseron.components.nvr import COMPONENT as NVR_COMPONENT
from viseron.components.storage.models import TriggerTypes
from viseron.components.telegram.ptz_control import TelegramPTZ
from viseron.components.telegram.utils import limit_user_access
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import (
    DOMAIN as CAMERA_DOMAIN,
    EVENT_RECORDER_COMPLETE,
)
from viseron.domains.camera.recorder import EventRecorderData, ManualRecording
from viseron.exceptions import ComponentNotReady, DomainNotRegisteredError
from viseron.helpers import escape_string
from viseron.helpers.logs import SensitiveInformationFilter
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict

from .const import (
    COMPONENT,
    CONFIG_CAMERAS,
    CONFIG_DETECTION_LABEL,
    CONFIG_DETECTION_LABEL_DEFAULT,
    CONFIG_PTZ_COMPONENT,
    CONFIG_SEND_MESSAGE,
    CONFIG_SEND_THUMBNAIL,
    CONFIG_SEND_VIDEO,
    CONFIG_TELEGRAM_BOT_TOKEN,
    CONFIG_TELEGRAM_CHAT_IDS,
    CONFIG_TELEGRAM_LOG_IDS,
    CONFIG_TELEGRAM_USER_IDS,
    DEFAULT_SEND_MESSAGE,
    DEFAULT_SEND_THUMBNAIL,
    DEFAULT_SEND_VIDEO,
    DEFAULT_TELEGRAM_LOG_IDS,
    DEFAULT_TELEGRAM_USER_IDS,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DETECTION_LABEL,
    DESC_SEND_MESSAGE,
    DESC_SEND_THUMBNAIL,
    DESC_SEND_VIDEO,
    DESC_TELEGRAM_BOT_TOKEN,
    DESC_TELEGRAM_CHAT_IDS,
    DESC_TELEGRAM_LOG_IDS,
    DESC_TELEGRAM_USER_IDS,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.components.nvr.nvr import NVR

LOGGER = logging.getLogger(__name__)

CAMERA_SCHEMA = vol.Schema(
    {},
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): {
            vol.Required(
                CONFIG_TELEGRAM_BOT_TOKEN, description=DESC_TELEGRAM_BOT_TOKEN
            ): str,
            vol.Required(
                CONFIG_TELEGRAM_CHAT_IDS, description=DESC_TELEGRAM_CHAT_IDS
            ): [int],
            vol.Optional(
                CONFIG_TELEGRAM_USER_IDS,
                description=DESC_TELEGRAM_USER_IDS,
                default=DEFAULT_TELEGRAM_USER_IDS,
            ): [int],
            vol.Optional(
                CONFIG_DETECTION_LABEL,
                description=DESC_DETECTION_LABEL,
                default=CONFIG_DETECTION_LABEL_DEFAULT,
            ): str,
            vol.Optional(
                CONFIG_SEND_THUMBNAIL,
                description=DESC_SEND_THUMBNAIL,
                default=DEFAULT_SEND_THUMBNAIL,
            ): bool,
            vol.Optional(
                CONFIG_SEND_VIDEO,
                description=DESC_SEND_VIDEO,
                default=DEFAULT_SEND_VIDEO,
            ): bool,
            vol.Optional(
                CONFIG_SEND_MESSAGE,
                description=DESC_SEND_MESSAGE,
                default=DEFAULT_SEND_MESSAGE,
            ): bool,
            vol.Optional(
                CONFIG_TELEGRAM_LOG_IDS,
                description=DESC_TELEGRAM_LOG_IDS,
                default=DEFAULT_TELEGRAM_LOG_IDS,
            ): bool,
            vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
                CameraIdentifier(): vol.All(CoerceNoneToDict(), CAMERA_SCHEMA),
            },
        }
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config: dict[str, Any]) -> bool:
    """Set up the telegram component."""
    component_config = config[COMPONENT]

    telegram_notifier = TelegramEventNotifier(vis, component_config)

    if not config.get(CONFIG_PTZ_COMPONENT):
        LOGGER.info("No PTZ component. Won't start Telegram PTZ Controller.")
        telegram_ptz = None
    else:
        if not vis.data.get(CONFIG_PTZ_COMPONENT):
            raise ComponentNotReady(
                f"PTZ component '{CONFIG_PTZ_COMPONENT}' not ready yet"
            )
        telegram_ptz = TelegramPTZ(vis, component_config, telegram_notifier)
        Thread(target=telegram_ptz.run_async).start()

    Thread(target=telegram_notifier.run_async).start()

    if telegram_ptz:
        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, telegram_ptz.stop)
    vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, telegram_notifier.stop)
    return True


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
    """
    Telegram event notifier class.

    This class sends notifications to a Telegram chat when an event occurs.
    """

    def __init__(self, vis: Viseron, config: dict[str, Any]) -> None:
        self._vis = vis
        self._config = config
        SensitiveInformationFilter.add_sensitive_string(
            self._config[CONFIG_TELEGRAM_BOT_TOKEN]
        )
        SensitiveInformationFilter.add_sensitive_string(
            escape_string(self._config[CONFIG_TELEGRAM_BOT_TOKEN])
        )
        self._bot_token = self._config[CONFIG_TELEGRAM_BOT_TOKEN]
        self._chat_ids = self._config[CONFIG_TELEGRAM_CHAT_IDS]
        self._loop = asyncio.new_event_loop()
        self._bot = Bot(token=self._bot_token)
        self._app = Application.builder().token(self._bot_token).build()
        self._stop_event = asyncio.Event()
        self._active_camera_identifier: str = (
            list(self._config[CONFIG_CAMERAS].keys())[0] or ""
        )
        for camera_identifier in self._config[CONFIG_CAMERAS]:
            self._vis.listen_event(
                EVENT_RECORDER_COMPLETE.format(camera_identifier=camera_identifier),
                self._recorder_complete_event,
            )
        vis.data[COMPONENT] = self

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

    async def _send_notifications(self, event_data: Event[EventRecorderData]) -> None:
        file = event_data.data.recording.clip_path
        if file and os.path.exists(file) and self._config[CONFIG_SEND_VIDEO]:
            caption = f"{event_data.data.camera.identifier}"
            if event_data.data.recording.objects:
                caption += f" detected a {event_data.data.recording.objects[0].label}"
            thumb = rescale_image_cv2(
                event_data.data.recording.thumbnail_path, max_size=320
            )
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
            and self._config[CONFIG_SEND_THUMBNAIL]
        ):
            for chat_id in self._chat_ids:
                await self._bot.send_photo(
                    chat_id=chat_id,
                    photo=open(event_data.data.recording.thumbnail_path, "rb"),
                    caption=f"Thumbnail for {event_data.data.camera.identifier}",
                )
        if self._config[CONFIG_SEND_MESSAGE]:
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
            if self._app.updater:
                await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    def run_async(self):
        """Run TelegramEventNotifier in a new event loop."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._listen())
        LOGGER.info("TelegramEventNotifier done")

    def stop(self) -> None:
        """Stop TelegramEventNotifier component."""
        self._stop_event.set()
        LOGGER.info("Stopping TelegramEventNotifier")

    def get_camera(self, camera_identifier: str) -> AbstractCamera | None:
        """Get camera instance."""
        try:
            return self._vis.get_registered_domain(CAMERA_DOMAIN, camera_identifier)
        except DomainNotRegisteredError:
            return None

    def get_cameras(self) -> None | dict[str, AbstractCamera]:
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
                    f"Active camera: {self.active_camera_identifier}"
                )
            else:
                await update.message.reply_text("No camera selected.")

    @limit_user_access
    async def _snapshot(self, update: Update, _context: CallbackContext) -> None:
        """Take a snapshot with the camera."""
        cam: AbstractCamera | None = self.get_camera(self.active_camera_identifier)
        if cam:
            ret, snapshot = cam.get_snapshot(cam.current_frame)
            if update.message and ret:
                await update.message.reply_photo(photo=snapshot)
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
                    await update.message.reply_text("Camera turned off.")
            else:
                cam.start_camera()
                if update.message:
                    await update.message.reply_text("Camera turned on.")

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

        nvr: NVR | None = self._vis.data[NVR_COMPONENT].get(cam.identifier, None)
        if nvr is None:
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
                    f"Started manual recording for camera {cam.identifier} with "
                    f"{f'duration {duration}s' if duration else 'no duration'}.",
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

        nvr: NVR | None = self._vis.data[NVR_COMPONENT].get(cam.identifier, None)
        if nvr is None:
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
                commands.append(f"{command_list} - {first_line_doc}")

        help_message = "\n".join(commands)
        help_message += "\nUse /help <command> to get more information about a command."
        await update.message.reply_text(help_message)
