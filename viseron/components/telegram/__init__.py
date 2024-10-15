"""PTZ over Telegram."""

from __future__ import annotations

import asyncio
import io
import logging
import os
from collections import defaultdict
from functools import wraps
from textwrap import dedent
from threading import Thread
from typing import TYPE_CHECKING

import cv2
import numpy as np
import voluptuous as vol
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
)

from viseron.components.ptz import PTZ
from viseron.components.storage.models import TriggerTypes
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import EVENT_RECORDER_COMPLETE
from viseron.domains.camera.recorder import EventRecorderData
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
            vol.Required(
                CONFIG_TELEGRAM_USER_IDS, description=DESC_TELEGRAM_USER_IDS
            ): [int],
            vol.Optional(
                CONFIG_DETECTION_LABEL,
                description=DESC_DETECTION_LABEL,
                default=CONFIG_DETECTION_LABEL_DEFAULT,
            ): str,
            vol.Optional(
                CONFIG_SEND_THUMBNAIL, description=DESC_SEND_THUMBNAIL, default=False
            ): bool,
            vol.Optional(
                CONFIG_SEND_VIDEO, description=DESC_SEND_VIDEO, default=False
            ): bool,
            vol.Optional(
                CONFIG_SEND_MESSAGE, description=DESC_SEND_MESSAGE, default=True
            ): bool,
            vol.Optional(
                CONFIG_TELEGRAM_LOG_IDS,
                description=DESC_TELEGRAM_LOG_IDS,
                default=False,
            ): bool,
            vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
                CameraIdentifier(): vol.All(CoerceNoneToDict(), CAMERA_SCHEMA),
            },
        }
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config) -> bool:
    """Set up the ptz component."""
    component_config = config[COMPONENT]

    if not config[CONFIG_PTZ_COMPONENT]:
        LOGGER.info("No PTZ component. Won't start Telegram PTZ Controller.")
    else:
        telegram_ptz = TelegramPTZ(vis, component_config)
        Thread(target=telegram_ptz.run_async).start()

    telegram_notifier = TelegramEventNotifier(vis, component_config)
    Thread(target=telegram_notifier.run_async).start()

    if telegram_ptz:
        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, telegram_ptz.stop)
    vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, telegram_notifier.stop)
    return True


def lissajous_curve(amp_x, amp_y, f_x, f_y, delta, t):
    """Compute x and y values for a Lissajous curve."""
    x = amp_x * np.sin(f_x * t + delta)
    y = amp_y * np.sin(f_y * t)
    return x, y


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

    def __init__(self, vis, config) -> None:
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
        self._stop_event = asyncio.Event()
        for camera_identifier in self._config[CONFIG_CAMERAS]:
            self._vis.listen_event(
                EVENT_RECORDER_COMPLETE.format(camera_identifier=camera_identifier),
                self._recorder_complete_event,
            )
        vis.data[COMPONENT] = self

    def _recorder_complete_event(self, event_data: Event[EventRecorderData]) -> None:
        asyncio.run_coroutine_threadsafe(
            self._send_notifications(event_data), self._loop
        )

    async def _send_notifications(self, event_data: Event[EventRecorderData]) -> None:
        file = event_data.data.recording.path
        if os.path.exists(file) and self._config[CONFIG_SEND_VIDEO]:
            caption = f"{event_data.data.camera.identifier}"
            if event_data.data.recording.objects:
                caption += f" detected a {event_data.data.recording.objects[0].label}"
            thumb = rescale_image_cv2(
                event_data.data.recording.thumbnail_path, max_size=320
            )
            for chat_id in self._chat_ids:
                await self._bot.send_video(
                    chat_id=chat_id,
                    thumbnail=thumb,  # is ignored by telegram for small videos :(
                    video=open(file, "rb"),
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

    async def _run_until_stopped(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(1)

    def run_async(self):
        """Run TelegramEventNotifier in a new event loop."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_until_stopped())
        LOGGER.info("TelegramEventNotifier done")

    def stop(self) -> None:
        """Stop TelegramEventNotifier component."""
        self._stop_event.set()
        LOGGER.info("Stopping TelegramEventNotifier")


def limit_user_access(func):
    """Limit user access to Telegram bot commands."""

    @wraps(func)
    async def wrapper(self, update: Update, context: CallbackContext, *args, **kwargs):
        if (
            # pylint: disable=protected-access
            update
            and update.effective_user
            and update.effective_user.id in self._config[CONFIG_TELEGRAM_USER_IDS]
        ):
            return await func(self, update, context, *args, **kwargs)

        user_id = update.effective_user.id if update.effective_user else "<unknown>"
        if update:
            # pylint: disable=protected-access
            if self._config[CONFIG_TELEGRAM_LOG_IDS]:
                LOGGER.warning(f"Access denied for user {user_id}.")
            if update.message:
                await update.message.reply_text(
                    text=f"Access denied for user {user_id}.",
                )

    return wrapper


class TelegramPTZ:
    """TelegramPTZ class allows control of p/t/z (and other stuff) over Telegram."""

    def __init__(self, vis, config) -> None:
        self._vis = vis
        self._config = config
        SensitiveInformationFilter.add_sensitive_string(
            self._config[CONFIG_TELEGRAM_BOT_TOKEN]
        )
        SensitiveInformationFilter.add_sensitive_string(
            escape_string(self._config[CONFIG_TELEGRAM_BOT_TOKEN])
        )
        self._bot_token = self._config[CONFIG_TELEGRAM_BOT_TOKEN]
        self._app: Application | None = None
        self._ptz: PTZ = self._vis.data[CONFIG_PTZ_COMPONENT]
        self._active_cam_ident: str = list(self._config[CONFIG_CAMERAS].keys())[0] or ""
        self._stop_event = asyncio.Event()
        vis.data[COMPONENT] = self

    async def _listen(self) -> None:
        """Start listening for commands from Telegram."""
        self._app = Application.builder().token(self._bot_token).build()
        self._app.add_handler(CommandHandler("left", self._pan_left))
        self._app.add_handler(CommandHandler("l", self._pan_left))
        self._app.add_handler(CommandHandler("right", self._pan_right))
        self._app.add_handler(CommandHandler("r", self._pan_right))
        self._app.add_handler(CommandHandler("up", self._tilt_up))
        self._app.add_handler(CommandHandler("u", self._tilt_up))
        self._app.add_handler(CommandHandler("down", self._tilt_down))
        self._app.add_handler(CommandHandler("d", self._tilt_down))
        self._app.add_handler(CommandHandler("patrol", self._patrol))
        self._app.add_handler(CommandHandler("p", self._patrol))
        self._app.add_handler(CommandHandler("zo", self._zoom_out))
        self._app.add_handler(CommandHandler("o", self._zoom_out))
        self._app.add_handler(CommandHandler("zi", self._zoom_in))
        self._app.add_handler(CommandHandler("i", self._zoom_in))
        self._app.add_handler(CommandHandler("record", self._record))
        self._app.add_handler(CommandHandler("r", self._record))
        self._app.add_handler(CommandHandler("list", self._list_cams))
        self._app.add_handler(CommandHandler("li", self._list_cams))
        self._app.add_handler(CommandHandler("select", self._list_cams))
        self._app.add_handler(CommandHandler("which", self._which_cam))
        self._app.add_handler(CommandHandler("w", self._which_cam))
        self._app.add_handler(CommandHandler("toggle", self._toggle_camera))
        self._app.add_handler(CommandHandler("t", self._toggle_camera))
        self._app.add_handler(CommandHandler("stop", self._stop_patrol))
        self._app.add_handler(CommandHandler("st", self._stop_patrol))
        self._app.add_handler(CommandHandler("pos", self._get_position))
        self._app.add_handler(CommandHandler("preset", self._preset))
        self._app.add_handler(CommandHandler("pr", self._preset))
        self._app.add_handler(CommandHandler("repeat", self._repeat_preset))
        self._app.add_handler(CommandHandler("snapshot", self._snapshot))
        self._app.add_handler(CommandHandler("lissa", self._lissa))
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

        LOGGER.info("Telegram PTZ Controller stopped")

    def stop(self) -> None:
        """Stop TelegramPTZ Controller."""
        self._stop_event.set()
        LOGGER.info("Stopping Telegram PTZ Controller")

    def run_async(self):
        """Run TelegramPTZ Controller in a new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._listen())
        LOGGER.info("TelegramPTZ Controller done")

    # pylint: disable=unused-argument
    @limit_user_access
    async def _pan_left(self, update: Update, context: CallbackContext) -> None:
        """
        Pan the camera to the left.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args and len(context.args) > 0:
            step_size = float(context.args[0])
        self._ptz.pan_left(
            camera_identifier=self._active_cam_ident, step_size=step_size
        )

    # pylint: disable=unused-argument
    @limit_user_access
    async def _pan_right(self, update: Update, context: CallbackContext) -> None:
        """
        Pan the camera to the right.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args and len(context.args) > 0:
            step_size = float(context.args[0])
        self._ptz.pan_right(
            camera_identifier=self._active_cam_ident, step_size=step_size
        )

    # pylint: disable=unused-argument
    @limit_user_access
    async def _tilt_up(self, update: Update, context: CallbackContext) -> None:
        """
        Tilt the camera up.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args and len(context.args) > 0:
            step_size = float(context.args[0])
        self._ptz.tilt_up(camera_identifier=self._active_cam_ident, step_size=step_size)

    # pylint: disable=unused-argument
    @limit_user_access
    async def _tilt_down(self, update: Update, context: CallbackContext) -> None:
        """
        Tilt the camera down.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args and len(context.args) > 0:
            step_size = float(context.args[0])
        self._ptz.tilt_down(
            camera_identifier=self._active_cam_ident, step_size=step_size
        )

    # pylint: disable=unused-argument
    @limit_user_access
    async def _zoom_out(self, update: Update, context: CallbackContext) -> None:
        """
        Zoom the camera out.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args and len(context.args) > 0:
            step_size = float(context.args[0])
        self._ptz.zoom_out(
            camera_identifier=self._active_cam_ident, step_size=step_size
        )

    # pylint: disable=unused-argument
    @limit_user_access
    async def _zoom_in(self, update: Update, context: CallbackContext) -> None:
        """
        Zoom the camera in.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args and len(context.args) > 0:
            step_size = float(context.args[0])
        self._ptz.zoom_in(camera_identifier=self._active_cam_ident, step_size=step_size)

    # pylint: disable=unused-argument
    @limit_user_access
    async def _list_cams(self, update: Update, context: CallbackContext) -> None:
        """
        List all available cameras.

        The user can select a camera to switch to by clicking on the camera name.
        """
        try:
            keyboard = []
            # Get all cameras registered with the PTZ component
            cameras = self._ptz.get_registered_cameras()
            # filter the registered cameras down to cameras that are active in config:
            cameras = {
                k: v for k, v in cameras.items() if k in self._config[CONFIG_CAMERAS]
            }
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
    async def _callback_parser(self, update: Update, context: CallbackContext) -> None:
        """Parse the callback data from the inline keyboard."""
        query = update.callback_query
        if query:
            await query.answer(read_timeout=30)
            self._active_cam_ident = str(query.data)
            await query.edit_message_text(text=f"Switched to camera {query.data}")

    @limit_user_access
    async def _get_position(self, update: Update, context: CallbackContext) -> None:
        """Get the current (PTZ) position of the camera."""
        x, y = self._ptz.get_position(self._active_cam_ident)
        if update.message:
            await update.message.reply_text(f"Position: {x}, {y}")

    @limit_user_access
    async def _patrol(self, update: Update, context: CallbackContext) -> None:
        """
        Swings the camera from left to right and back, etc.

        @param duration: The duration of the patrol in seconds
        @param sleep_after_swing: The time to sleep after each swing in seconds
        @param step_size: The size of each move step
        @param step_sleep_time: Time to sleep between each move step

        parameters are passed in the Telegram message e.g.:

        /patrol 60

        This will swing the camera back and forth for 60 seconds with a 6 second pause.

        /patrol 60 10

        This will swing the camera back and forth for 60 seconds with a 10 second pause.

        /patrol 60 6 0.3

        This will swing the camera back and forth for 60 seconds with a 6 second pause
        after each completed swing. Each step will be 0.3 in size and the move will
        pause for 0.1 seconds between each step.

        /patrol 0 10 0.3 5.0

        This will swing the camera back and forth indefinitely with a 10 second pause
        after each completed swing. Each step will be 0.3 in size and the move will
        pause for 5 seconds between each step.

        When the patrol is stopped, the camera will return to its initial position.
        """

        duration = 5
        sleep_after_swing = 6
        step_size = 0.1
        step_sleep_time = 0.1
        if context.args and len(context.args) > 0:
            duration = int(context.args[0])
        if context.args and len(context.args) > 1:
            sleep_after_swing = int(context.args[1])
        if context.args and len(context.args) > 2:
            step_size = float(context.args[2])
        if context.args and len(context.args) > 3:
            step_sleep_time = float(context.args[3])
        await self._ptz.patrol(
            camera_identifier=self._active_cam_ident,
            duration=duration,
            sleep_after_swing=sleep_after_swing,
            step_size=step_size,
            step_sleep_time=step_sleep_time,
        )

    # pylint: disable=unused-argument
    @limit_user_access
    async def _stop_patrol(self, update: Update, context: CallbackContext) -> None:
        """Stop the patrol."""
        self._ptz.stop_patrol(self._active_cam_ident)

    @limit_user_access
    async def _lissa(self, update: Update, context: CallbackContext) -> None:
        """
        Perform Lissajous curve swing patrols.

        Amplitude determines the maximum displacement from the center position.
        For example, if the amplitude is 1.0, the movement will range from -1.0 to 1.0.
        If the amplitude is 0.5, the movement will range from -0.5 to 0.5.

        @param pan_amp: The amplitude of the pan movement.
        Increasing the pan amplitude makes the horizontal oscillation wider.
        The camera will pan further to the left and right.

        Frequency determines the speed of the oscillations.
        Higher frequencies result in faster oscillations, while lower frequencies result
        in slower oscillations.

        @param pan_freq: The frequency of the pan movement.
        Increasing the pan frequency makes the horizontal oscillation occur more
        rapidly. The camera will pan back and forth faster.

        @param tilt_amp: The amplitude of the tilt movement.
        Increasing the tilt amplitude makes the vertical oscillation wider.
        The camera will tilt further up and down.

        @param tilt_freq: The frequency of the tilt movement.
        Increasing the tilt frequency makes the vertical oscillation occur more rapidly.
        The camera will tilt up and down faster.

        @param phase_shift: The phase shift of the pan movement.
        The phase shift determines the relative displacement between the two
        oscillations at a given time. It affects the overall shape and orientation of
        the Lissajous figure.

        The phase shift is an angular offset applied to one of the oscillations (pan)
        relative to the other (tilt). It changes where one oscillation starts relative
        to the other.

        The default phase shift is pi/2, which means the pan oscillation starts a
        quarter cycle ahead of the tilt oscillation. The resulting figure can resemble
        a figure eight or other intricate patterns.

        Phase shift 0: pan and tilt oscillations start at the same point. Shapes are
        straight lines or an ellipse.

        A phase shift of pi: one oscillation starts half cycle ahead of the other.
        The resulting figure can look an inverted version of the original shape without
        phase shift.

        @param step_sleep_time: Time to sleep between each move step.

        Parameters are passed through the Telegram message e.g.:

        /lissa 1.0 0.1 1.0 0.1 1.5708 0.1

        This will perform a Lissajous curve patrol with the following parameters:
        - Pan amplitude: 1.0
        - Pan frequency: 0.1
        - Tilt amplitude: 1.0
        - Tilt frequency: 0.1
        - Phase shift: 1.5708 (pi/2)
        - Step sleep time: 0.1

        The resulting Lissajous curve will be displayed as a photo in the chat.
        """
        pan_amp = 1.0
        pan_freq = 0.1
        tilt_amp = 1.0
        tilt_freq = 0.1
        phase_shift = np.pi / 2
        step_sleep_time = 0.1

        if context.args and len(context.args) > 0:
            pan_amp = float(context.args[0])
        if context.args and len(context.args) > 1:
            pan_freq = float(context.args[1])
        if context.args and len(context.args) > 2:
            tilt_amp = float(context.args[2])
        if context.args and len(context.args) > 3:
            tilt_freq = float(context.args[3])
        if context.args and len(context.args) > 4:
            phase_shift = float(context.args[4])
        if context.args and len(context.args) > 5:
            step_sleep_time = float(context.args[5])

        # Generate Lissajous curve for visualization
        t = np.linspace(0, 100, 1000)
        x, y = lissajous_curve(pan_amp, tilt_amp, pan_freq, tilt_freq, phase_shift, t)

        # Normalize and scale the curve to fit in the image
        x = np.interp(x, (x.min(), x.max()), (0, 250))
        y = np.interp(y, (y.min(), y.max()), (0, 250))

        # Create a blank image
        image = np.ones((250, 250, 3), dtype=np.uint8) * 255

        # Draw the curve
        for i in range(len(x) - 1):
            cv2.line(
                image,
                (int(x[i]), int(y[i])),
                (int(x[i + 1]), int(y[i + 1])),
                (0, 0, 255),
                2,
            )

        if update.message:
            # Encode the image to a memory buffer
            is_success, buffer = cv2.imencode(".png", image)
            if is_success and buffer is not None:
                io_buf = io.BytesIO(buffer)  # type: ignore[arg-type]
                await update.message.reply_photo(photo=io_buf)

        await self._ptz.lissajous_curve_patrol(
            camera_identifier=self._active_cam_ident,
            pan_amp=pan_amp,
            pan_freq=pan_freq,
            tilt_amp=tilt_amp,
            tilt_freq=tilt_freq,
            phase_shift=phase_shift,
            step_sleep_time=step_sleep_time,
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
        duration = 5
        number_of_videos = 1
        if context.args and len(context.args) > 0:
            duration = int(context.args[0])
        if context.args and len(context.args) > 1:
            number_of_videos = int(context.args[1])
        cam: AbstractCamera | None = self._ptz.get_camera(self._active_cam_ident)
        if cam is None:
            if update.message:
                await update.message.reply_text("Camera not found.")
            return

        if cam.is_recording:
            if update.message:
                await update.message.reply_text("Camera is already recording.")
            return
        if cam.current_frame is None:
            if update.message:
                await update.message.reply_text("No frame available.")
            return
        for _ in range(number_of_videos):
            recording = cam.recorder.start(
                shared_frame=cam.current_frame,
                trigger_type=TriggerTypes.OBJECT,
                objects_in_fov=[],
            )
            await asyncio.sleep(duration)
            if cam.recorder.is_recording:
                cam.recorder.stop(recording)

    @limit_user_access
    async def _which_cam(self, update: Update, context: CallbackContext) -> None:
        """Get the currently active camera."""
        if update.message:
            if self._active_cam_ident:
                await update.message.reply_text(
                    f"Active camera: {self._active_cam_ident}"
                )
            else:
                await update.message.reply_text("No camera selected.")

    @limit_user_access
    async def _toggle_camera(self, update: Update, context: CallbackContext) -> None:
        """Toggle the camera on or off."""
        cam: AbstractCamera | None = self._ptz.get_camera(self._active_cam_ident)
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
    async def _preset(self, update: Update, context: CallbackContext) -> None:
        """
        Change the camera to a preset position.

        Use /preset <name> to move the camera to a preset position.
        Use /preset list to get a list of available presets.
        """
        name = "list" if not context.args else context.args[0]
        if name == "list":
            presets = self._ptz.get_presets(self._active_cam_ident)
            preset_cmds = "\n".join(f"/preset {preset}" for preset in presets)
            if update.message:
                await update.message.reply_text(f"Available presets:\n{preset_cmds}")
                return

        could_complete = await self._ptz.move_to_preset_wait_complete(
            camera_identifier=self._active_cam_ident, preset_name=name
        )
        if update.message:
            if could_complete:
                await update.message.reply_text(f"Moved to preset '{name}'")
            else:
                await update.message.reply_text(f"Failed to move to preset '{name}'")

    @limit_user_access
    async def _repeat_preset(self, update: Update, context: CallbackContext) -> None:
        """
        Presets are paths when names are reused.

        Use /repeat to repeat the preset path a number of times.
        @param name: The name of the preset to repeat.
        @param repeat_count: The number of times to repeat the preset (path) default 5.
        E.g.
        /repeat name 10
        will repeat the preset (path) 'name' 10 times.
        """
        name = "list" if not context.args else context.args[0]
        if name == "list":
            presets = self._ptz.get_presets(self._active_cam_ident)
            preset_cmds = "\n".join(f"/preset {preset}" for preset in presets)
            if update.message:
                await update.message.reply_text(f"Available presets:\n{preset_cmds}")
                return
        repeat_count = 5
        if context.args and len(context.args) > 1:
            repeat_count = int(context.args[1])

        async def run_presets_sequentially():
            for _ in range(repeat_count):
                await self._ptz.move_to_preset_wait_complete(
                    camera_identifier=self._active_cam_ident, preset_name=name
                )

        # Schedule the task to run in the background
        asyncio.create_task(run_presets_sequentially())

        # Return immediately
        if update.message:
            await update.message.reply_text(f"Started repeating preset '{name}'")

    @limit_user_access
    async def _snapshot(self, update: Update, context: CallbackContext) -> None:
        """Take a snapshot with the camera."""
        cam: AbstractCamera | None = self._ptz.get_camera(self._active_cam_ident)
        if cam:
            ret, snapshot = cam.get_snapshot(cam.current_frame)
            if update.message and ret:
                await update.message.reply_photo(photo=snapshot)
        else:
            if update.message:
                await update.message.reply_text("No active camera.")

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
