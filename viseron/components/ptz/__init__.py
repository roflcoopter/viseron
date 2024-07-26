"""PTZ interface."""

from __future__ import annotations

import asyncio
import logging
from threading import Thread
from typing import TYPE_CHECKING

import voluptuous as vol
from onvif import ONVIFCamera, ONVIFError, ONVIFService
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
)

from viseron.const import VISERON_SIGNAL_SHUTDOWN

from .const import (
    COMPONENT,
    CONFIG_CAMERA_FULL_SWING_MAX_X,
    CONFIG_CAMERA_FULL_SWING_MIN_X,
    CONFIG_CAMERA_IP,
    CONFIG_CAMERA_NAME,
    CONFIG_CAMERA_PASSWORD,
    CONFIG_CAMERA_PORT,
    CONFIG_CAMERA_USERNAME,
    CONFIG_CAMERAS,
    CONFIG_TELEGRAM_BOT_TOKEN,
    DESC_CAMERA_FULL_SWING_MAX_X,
    DESC_CAMERA_FULL_SWING_MIN_X,
    DESC_CAMERA_IP,
    DESC_CAMERA_NAME,
    DESC_CAMERA_PASSWORD,
    DESC_CAMERA_PORT,
    DESC_CAMERA_USERNAME,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_TELEGRAM_BOT_TOKEN,
)

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): {
            vol.Required(
                CONFIG_TELEGRAM_BOT_TOKEN, description=DESC_TELEGRAM_BOT_TOKEN
            ): str,
            vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): vol.All(
                [
                    vol.Schema(
                        {
                            vol.Optional(
                                CONFIG_CAMERA_NAME, description=DESC_CAMERA_NAME
                            ): str,
                            vol.Required(
                                CONFIG_CAMERA_IP, description=DESC_CAMERA_IP
                            ): str,
                            vol.Required(
                                CONFIG_CAMERA_PORT, description=DESC_CAMERA_PORT
                            ): int,
                            vol.Required(
                                CONFIG_CAMERA_USERNAME, description=DESC_CAMERA_USERNAME
                            ): str,
                            vol.Required(
                                CONFIG_CAMERA_PASSWORD, description=DESC_CAMERA_PASSWORD
                            ): str,
                            vol.Optional(
                                CONFIG_CAMERA_FULL_SWING_MIN_X,
                                description=DESC_CAMERA_FULL_SWING_MIN_X,
                            ): float,
                            vol.Optional(
                                CONFIG_CAMERA_FULL_SWING_MAX_X,
                                description=DESC_CAMERA_FULL_SWING_MAX_X,
                            ): float,
                        }
                    )
                ],
                vol.Length(min=1),  # Ensure at least one camera is defined
            ),
        },
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config) -> bool:
    """Set up the ptz component."""
    config = config[COMPONENT]
    ptz_controller = PTZ(vis, config)
    Thread(target=ptz_controller.run_async).start()
    vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, ptz_controller.stop)
    return True


class PTZ:
    """PTZ class allows control of pan/tilt/zoom over Telegram."""

    def __init__(self, vis, config) -> None:
        self._vis = vis
        self._config = config
        self._bot_token = self._config[CONFIG_TELEGRAM_BOT_TOKEN]
        self._cameras = self._config[CONFIG_CAMERAS]
        self._active_cam_index = 0
        self._active_cam: ONVIFCamera | None = None
        self._ptz_service: ONVIFService | None = None
        self._ptz_token = None
        self._app: Application | None = None
        self._kill_received = False
        vis.data[COMPONENT] = self
        self._initialize_camera(self._active_cam_index)

    def _initialize_camera(self, index):
        camera_config = self._cameras[index]
        self._active_cam_index = index
        ip = camera_config[CONFIG_CAMERA_IP]
        port = camera_config[CONFIG_CAMERA_PORT]
        user = camera_config[CONFIG_CAMERA_USERNAME]
        pw = camera_config[CONFIG_CAMERA_PASSWORD]
        self._active_cam = ONVIFCamera(ip, port, user, pw)
        self._ptz_service = self._active_cam.create_ptz_service()
        self._ptz_token = self._get_ptz_token()
        self._stop_patrol_event = asyncio.Event()

    def _get_ptz_token(self):
        if self._active_cam is not None:
            media_service = self._active_cam.create_media_service()
            profiles = media_service.GetProfiles()
            if profiles:
                return profiles[0].token
        raise RuntimeError("No profiles found for the camera")

    async def listen(self) -> None:
        """Start listening for commands from Telegram."""
        self._app = Application.builder().token(self._bot_token).build()
        self._app.add_handler(CommandHandler("left", self.pan_left))
        self._app.add_handler(CommandHandler("l", self.pan_left))
        self._app.add_handler(CommandHandler("right", self.pan_right))
        self._app.add_handler(CommandHandler("r", self.pan_right))
        self._app.add_handler(CommandHandler("up", self.tilt_up))
        self._app.add_handler(CommandHandler("u", self.tilt_up))
        self._app.add_handler(CommandHandler("down", self.tilt_down))
        self._app.add_handler(CommandHandler("d", self.tilt_down))
        self._app.add_handler(CommandHandler("patrol", self.patrol))
        self._app.add_handler(CommandHandler("p", self.patrol))
        self._app.add_handler(CommandHandler("zo", self.zoom_out))
        self._app.add_handler(CommandHandler("o", self.zoom_out))
        self._app.add_handler(CommandHandler("zi", self.zoom_in))
        self._app.add_handler(CommandHandler("i", self.zoom_in))
        self._app.add_handler(CommandHandler("record", self.record))
        self._app.add_handler(CommandHandler("r", self.record))
        self._app.add_handler(CommandHandler("list", self.list_cams))
        self._app.add_handler(CommandHandler("li", self.list_cams))
        self._app.add_handler(CommandHandler("cam", self.switch_cam))
        self._app.add_handler(CommandHandler("c", self.switch_cam))
        self._app.add_handler(CommandHandler("switch", self.switch_cam))
        self._app.add_handler(CommandHandler("sw", self.switch_cam))
        self._app.add_handler(CommandHandler("stop", self.stop_patrol))
        self._app.add_handler(CommandHandler("st", self.stop_patrol))
        self._app.add_handler(CommandHandler("pos", self.get_position))
        self._app.add_handler(CallbackQueryHandler(self.callback_parser))

        try:
            await self._app.initialize()
            await self._app.start()
            if self._app.updater:
                await self._app.updater.start_polling()
            else:
                raise RuntimeError("Updater not found")

            while not self._kill_received:
                await asyncio.sleep(1)
        finally:
            if self._app.updater:
                await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

        LOGGER.info("PTZ Controller stopped")

    def stop(self) -> None:
        """Stop PTZ Controller."""
        self._kill_received = True
        self._stop_patrol_event.set()
        LOGGER.info("Stopping PTZ Controller")

    def run_async(self):
        """Run PTZ Controller in a new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.listen())
        LOGGER.info("PTZ Controller done")

    async def _do_patrol(self, sleep_after_swing=6):
        """Perform a patrol of the camera."""
        try:
            if self._ptz_service is None:
                LOGGER.error("No PTZ service found")
                return
            status = self._ptz_service.GetStatus({"ProfileToken": self._ptz_token})
            current_x = status.Position.PanTilt.x
            current_y = status.Position.PanTilt.y
            LOGGER.info(f"Camera position at start of patrol: {current_x}, {current_y}")
            min_x = self._cameras[self._active_cam_index].get(
                CONFIG_CAMERA_FULL_SWING_MIN_X
            )
            max_x = self._cameras[self._active_cam_index].get(
                CONFIG_CAMERA_FULL_SWING_MAX_X
            )

            distance_to_min = current_x - min_x if min_x else 0
            distance_to_max = max_x - current_x if max_x else 0
            left = distance_to_min > distance_to_max

            while not self._stop_patrol_event.is_set():
                await self.full_swing(left, 0.1, min_x, max_x)
                if self._stop_patrol_event.is_set():
                    break
                await asyncio.sleep(sleep_after_swing)
                left = not left

        finally:
            # Problem here, this can be a different camera now - if not too much
            # overhead, maybe create and keep ONVIFCamera instances (and services) for
            # all cameras in the config

            # Anyway, move back to the initial position
            await self.absolute_move(current_x, current_y, current_y)

    async def full_swing(
        self,
        is_left: bool = True,
        step_size: float = 0.1,
        sleep_time: float = 0.1,
        min_x: float | None = None,
        max_x: float | None = None,
    ):
        """Perform a full swing in the pan direction.

        @param is_left: True if the swing is to the left, False if to the right
        @param step_size: The size of each move step
        @param sleep_time: Time to sleep between each move step
        @param min_x: Minimum x value to stop at, meant to be used to avoid going beyond
          the camera's limits or field of view
        @param max_x: Maximum x value to stop at

        """
        if self._ptz_service is None:
            LOGGER.error("No PTZ service found")
            return
        status = self._ptz_service.GetStatus({"ProfileToken": self._ptz_token})
        current_x = status.Position.PanTilt.x
        LOGGER.info(f"Fullswing start: x: {current_x}, min_x: {min_x}, max_x: {max_x}")

        move_step = -abs(step_size) if is_left else abs(step_size)

        if is_left:
            if min_x is not None and current_x + move_step <= min_x:
                return
        else:
            if max_x is not None and current_x + move_step >= max_x:
                return

        while (
            self.relative_move(move_step, 0.0) and not self._stop_patrol_event.is_set()
        ):
            await asyncio.sleep(sleep_time)
            status = self._ptz_service.GetStatus({"ProfileToken": self._ptz_token})
            current_x = status.Position.PanTilt.x
            LOGGER.info(
                f"Fullswing moved to: x: {current_x}, min_x: {min_x}, max_x: {max_x}"
            )
            if min_x is not None and current_x <= min_x:
                break
            if max_x is not None and current_x >= max_x:
                break

        LOGGER.info(f"Fullswing end: x: {current_x}, min_x: {min_x}, max_x: {max_x}")

    def relative_move(self, x, y) -> bool:
        """Move the camera relative to its current position."""
        if self._ptz_service is None:
            LOGGER.error("No PTZ service found")
            return False
        try:
            self._ptz_service.RelativeMove(
                {
                    "ProfileToken": self._ptz_token,
                    "Translation": {
                        "PanTilt": {"x": x, "y": y},
                        "Zoom": {"x": 0.0},
                    },
                }
            )
            return True
        except ONVIFError as e:
            # errors occur when the move exceeds the camera's limits, silence them
            LOGGER.debug(e)
            return False

    def zoom(self, zoom: float = 0.1) -> bool:
        """Zoom the camera in our out."""
        if self._ptz_service is None:
            LOGGER.error("No PTZ service found")
            return False
        try:
            self._ptz_service.RelativeMove(
                {
                    "ProfileToken": self._ptz_token,
                    "Translation": {
                        "PanTilt": {"x": 0.0, "y": 0.0},
                        "Zoom": {"x": zoom},
                    },
                }
            )
            return True
        except ONVIFError as e:
            # errors occur when the zoom exceeds the camera's limits, silence them
            # can't check, camera does not support zoom
            LOGGER.debug(e)
            return False

    async def absolute_move(self, x, y, zoom):
        """Move the camera to an absolute position."""
        if self._ptz_service is None:
            LOGGER.error("No PTZ service found")
            return False
        try:
            self._ptz_service.AbsoluteMove(
                {
                    "ProfileToken": self._ptz_token,
                    "Position": {
                        "PanTilt": {"x": x, "y": y},
                        "Zoom": {"x": zoom},
                    },
                }
            )
        except ONVIFError as e:
            LOGGER.error(e)

    async def continuous_move(self, x, y, seconds):
        """Move the camera continuously for a set amount of time."""
        if self._ptz_service is None:
            LOGGER.error("No PTZ service found")
            return False
        try:
            self._ptz_service.ContinuousMove(
                {
                    "ProfileToken": self._ptz_token,
                    "Velocity": {
                        "PanTilt": {"x": x, "y": y},
                        "Zoom": {"x": 0.0},
                    },
                }
            )
            await asyncio.sleep(seconds)
            self._ptz_service.Stop({"ProfileToken": self._ptz_token})
        except ONVIFError as e:
            LOGGER.error(e)

    # pylint: disable=unused-argument
    async def pan_left(self, update: Update, context: CallbackContext) -> None:
        """Pan the camera to the left."""
        self.relative_move(x=-0.1, y=0.0)

    # pylint: disable=unused-argument
    async def pan_right(self, update: Update, context: CallbackContext) -> None:
        """Pan the camera to the right."""
        self.relative_move(x=0.1, y=0.0)

    # pylint: disable=unused-argument
    async def tilt_up(self, update: Update, context: CallbackContext) -> None:
        """Tilt the camera up."""
        self.relative_move(x=0.0, y=0.1)

    # pylint: disable=unused-argument
    async def tilt_down(self, update: Update, context: CallbackContext) -> None:
        """Tilt the camera down."""
        self.relative_move(x=0.0, y=-0.1)

    # pylint: disable=unused-argument
    async def zoom_out(self, update: Update, context: CallbackContext) -> None:
        """Zoom the camera out."""
        self.zoom(-0.1)

    # pylint: disable=unused-argument
    async def zoom_in(self, update: Update, context: CallbackContext) -> None:
        """Zoom the camera in."""
        self.zoom(0.1)

    # pylint: disable=unused-argument
    async def patrol(self, update: Update, context: CallbackContext) -> None:
        """
        Swings the camera from left to right and back, etc.

        @param duration: The duration of the patrol in seconds
        @param sleep_time: The time to sleep after each swing in seconds

        parameters are passed in the Telegram message e.g.:

        /patrol 60 6

        This will swing the camera back and forth for 60 seconds with a 6 second sleep
        after each swing.

        """
        duration = 60 * 60 * 24  # default to 24 hours
        sleep_time = 6
        if context.args and len(context.args) == 1:
            duration = int(context.args[0])
        elif context.args and len(context.args) == 2:
            duration = int(context.args[0])
            sleep_time = int(context.args[1])
        self._stop_patrol_event.clear()
        await self._fire_and_forget(
            self._do_patrol, duration, sleep_after_swing=sleep_time
        )

    async def _fire_and_forget(self, coro, timeout, *args, **kwargs):
        """Fire and forget a coroutine with a timeout."""
        task = asyncio.create_task(coro(*args, **kwargs))
        asyncio.create_task(self._timeout_task(task, timeout))

    async def _timeout_task(self, task, timeout):
        """
        Cancel a task after a set amount of time if given.

        If not given, the task will run indefinitely.
        """
        if timeout > 0:
            await asyncio.sleep(timeout)
            if not task.done():
                task.cancel()

    async def stop_patrol(self, update: Update, context: CallbackContext) -> None:
        """Stop the patrol."""
        self._stop_patrol_event.set()
        if update.message:
            await update.message.reply_text("All patrols stopping.")

    # pylint: disable=unused-argument
    async def list_cams(self, update: Update, context: CallbackContext) -> None:
        """
        List all available cameras.

        The user can select a camera to switch to by clicking on the camera name.
        """
        try:
            # create a numbered list of available cameras based on the config
            cams = "\n".join(
                [
                    f"""
                    {i+1}: {c[CONFIG_CAMERA_NAME]
                            if c[CONFIG_CAMERA_NAME]
                            else c[CONFIG_CAMERA_IP]}
                    """
                    for i, c in enumerate(self._cameras)
                ]
            )
            keyboard = []
            for i, cam in enumerate(self._cameras):
                camera_name = cam[CONFIG_CAMERA_NAME] or f"Camera {i+1}"
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"{camera_name}",
                            callback_data=f"{i+1}",
                        )
                    ]
                )
            if update.message:
                await update.message.reply_text(
                    f"Available cameras:\n{cams}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
        except TelegramError as e:
            LOGGER.error(e)

    # pylint: disable=unused-argument
    async def callback_parser(self, update: Update, context: CallbackContext) -> None:
        """Parse the callback data from the inline keyboard."""
        query = update.callback_query
        if query:
            await query.answer(read_timeout=5)
            self._initialize_camera(int(str(query.data)) - 1)
            cam_name = self._cameras[int(str(query.data)) - 1][CONFIG_CAMERA_NAME]
            await query.edit_message_text(
                text=f"Switched to camera {cam_name if cam_name else query.data}"
            )

    async def switch_cam(self, update: Update, context: CallbackContext) -> None:
        """Switch to a different camera."""
        try:
            if not context.args or len(context.args) == 0:
                if update.message:
                    await update.message.reply_text("Please provide a camera index")
                return
            index = int(context.args[0]) - 1
            if 0 <= index < len(self._cameras):
                self._initialize_camera(index)
            else:
                if update.message:
                    await update.message.reply_text("Camera index out of range")

            cam_name = self._cameras[index][CONFIG_CAMERA_NAME]
            if update.message:
                await update.message.reply_text(
                    f"Switched to {cam_name if cam_name else f'camera {index+1}'}"
                )
        except TelegramError as e:
            LOGGER.error(e)

    # pylint: disable=unused-argument
    async def get_position(self, update: Update, context: CallbackContext) -> None:
        """Get the current position of the camera."""
        if self._ptz_service is None:
            LOGGER.error("No PTZ service found")
            return
        try:
            status = self._ptz_service.GetStatus({"ProfileToken": self._ptz_token})
            current_x = status.Position.PanTilt.x
            current_y = status.Position.PanTilt.y
            if update.message:
                await update.message.reply_text(
                    f"Position: x: {current_x}, y: {current_y}"
                )
        except ONVIFError as e:
            LOGGER.error(e)

    async def record(self, update: Update, context: CallbackContext) -> None:
        """
        Record a video from the camera.

        @param duration: The duration of the recording in seconds

        Parameters are passed through the Telegram message e.g.:

        /record 60

        This will record a video for 60 seconds and return it.
        """
        # Would love to know how to implement this
        # update.message.reply_video("")
