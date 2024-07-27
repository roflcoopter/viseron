"""PTZ interface."""

from __future__ import annotations

import asyncio
import io
import logging
from threading import Thread
from typing import TYPE_CHECKING

import cv2
import numpy as np
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


def lissajous_curve(amp_x, amp_y, f_x, f_y, delta, t):
    """Compute x and y values for a Lissajous curve."""
    x = amp_x * np.sin(f_x * t + delta)
    y = amp_y * np.sin(f_y * t)
    return x, y


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
        self._app.add_handler(CommandHandler("lissa", self.polissa))
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

    async def _do_patrol(
        self, step_size: float = 0.1, step_sleep_time: float = 0.1, sleep_after_swing=6
    ):
        """
        Perform a patrol of the camera.

        Swings the camera from left to right and back, etc. within the camera's limits,
        either by design or configuration (see minx_x, max_x).

        @param step_size: The size of each move step
        @param step_sleep_time: Time to sleep between each move step
        @param sleep_after_swing: Time to pause after each swing
        """
        try:

            # No service, no service
            if self._ptz_service is None:
                LOGGER.error("No PTZ service found")
                return

            # Get and store starting position
            status = self._ptz_service.GetStatus({"ProfileToken": self._ptz_token})
            current_x = status.Position.PanTilt.x
            current_y = status.Position.PanTilt.y
            LOGGER.debug(
                f"Camera position at start of patrol: x: {current_x}, y: {current_y}"
            )

            # Get the camera's FOV limits, if any.
            min_x = self._cameras[self._active_cam_index].get(
                CONFIG_CAMERA_FULL_SWING_MIN_X
            )
            max_x = self._cameras[self._active_cam_index].get(
                CONFIG_CAMERA_FULL_SWING_MAX_X
            )

            # Decide which direction to start swinging based on the distance to the
            # camera's FOV limits, left if closer to min_x, right if closer to max_x
            distance_to_min = current_x - min_x if min_x else 0
            distance_to_max = max_x - current_x if max_x else 0
            left = distance_to_min > distance_to_max

            # Swing back and forth until stopped
            while not self._stop_patrol_event.is_set():
                await self.full_swing(
                    is_left=left,
                    step_size=step_size,
                    step_sleep_time=step_sleep_time,
                    min_x=min_x,
                    max_x=max_x,
                )
                if self._stop_patrol_event.is_set():
                    break
                await asyncio.sleep(sleep_after_swing)
                left = not left

        finally:
            # Problem here, this can be a different camera now - if not too much
            # overhead, maybe create and keep ONVIFCamera instances (and services) for
            # all cameras in the config

            # Anyway, move back to the initial position
            await self.absolute_move(current_x, current_y)

    async def full_swing(
        self,
        is_left: bool = True,
        step_size: float = 0.1,
        step_sleep_time: float = 0.1,
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

        # No service, no service
        if self._ptz_service is None:
            LOGGER.error("No PTZ service found")
            return

        # Get and store starting position
        status = self._ptz_service.GetStatus({"ProfileToken": self._ptz_token})
        current_x = status.Position.PanTilt.x
        LOGGER.debug(f"Fullswing start: x: {current_x}, min_x: {min_x}, max_x: {max_x}")

        move_step = -abs(step_size) if is_left else abs(step_size)

        # Do not move beyond the camera's FOV bounds
        if is_left:
            if min_x is not None and current_x + move_step <= min_x:
                return
        else:
            if max_x is not None and current_x + move_step >= max_x:
                return

        # Move while not stopped or stopped by the camera's FOV or hardware bounds
        # Unsure how this will react to 360 (or more?) degree cameras
        while (
            self.relative_move(x=move_step, y=0.0)
            and not self._stop_patrol_event.is_set()
        ):
            await asyncio.sleep(step_sleep_time)
            status = self._ptz_service.GetStatus({"ProfileToken": self._ptz_token})
            current_x = status.Position.PanTilt.x
            LOGGER.debug(
                f"Fullswing moved to: x: {current_x}, min_x: {min_x}, max_x: {max_x}"
            )
            if min_x is not None and current_x <= min_x:
                break
            if max_x is not None and current_x >= max_x:
                break

        LOGGER.debug(f"Fullswing end: x: {current_x}, min_x: {min_x}, max_x: {max_x}")

    def relative_move(self, x: float, y: float) -> bool:
        """
        Move the camera relative to its current position.

        @param x: The relative x position to move to
        @param y: The relative y position to move to
        @return: True if the move was successful, False otherwise
        """
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
            # errors occur when the zoom exceeds the camera's limits?, silence them
            # can't check, camera does not support zoom
            LOGGER.debug(e)
            return False

    def absolute_move(self, x: float, y: float):
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
                        "Zoom": {"x": 0.0},  # or leave unchanged?
                    },
                }
            )
        except ONVIFError as e:
            LOGGER.error(e)

    async def continuous_move(self, x_velocity: float, y_velocity: float, seconds):
        """Move the camera continuously for a set amount of time."""
        if self._ptz_service is None:
            LOGGER.error("No PTZ service found")
            return False
        try:
            self._ptz_service.ContinuousMove(
                {
                    "ProfileToken": self._ptz_token,
                    "Velocity": {
                        "PanTilt": {"x": x_velocity, "y": y_velocity},
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
        @param sleep_after_swing: The time to sleep after each swing in seconds
        @param step_size: The size of each move step
        @param step_sleep_time: Time to sleep between each move step

        parameters are passed in the Telegram message e.g.:

        /patral 60

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
        duration = 60 * 60 * 24  # default to 24 hours
        sleep_after_swing = 6
        if context.args and len(context.args) > 0:
            duration = int(context.args[0])
        if context.args and len(context.args) > 1:
            sleep_after_swing = int(context.args[1])
        if context.args and len(context.args) > 2:
            step_size = float(context.args[2])
        if context.args and len(context.args) > 3:
            step_sleep_time = float(context.args[3])
        self._stop_patrol_event.clear()
        await self._fire_and_forget(
            self._do_patrol,
            duration,
            sleep_after_swing=sleep_after_swing,
            step_size=step_size,
            step_sleep_time=step_sleep_time,
        )

    async def _fire_and_forget(self, coro, timeout, *args, **kwargs):
        """Fire and forget a coroutine with a timeout."""
        coro_task = asyncio.create_task(coro(*args, **kwargs))
        # If a timeout is given, create a task to cancel the coroutine after the timeout
        if timeout > 0:
            asyncio.create_task(self._timeout_task(coro_task, timeout))

    async def _timeout_task(self, task, timeout):
        """Cancel a task after a set amount of time if given."""
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
                    f"{i+1}: {cam[CONFIG_CAMERA_NAME] or cam[CONFIG_CAMERA_IP]}"
                    for i, cam in enumerate(self._cameras)
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
            # Until we have a better way to handle this, stop the patrol,
            # otherwise the swings would be switched to the new camera
            self._stop_patrol_event.set()
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
                # Until we have a better way to handle this, stop the patrol,
                self._stop_patrol_event.set()
                self._initialize_camera(index)
            else:
                if update.message:
                    await update.message.reply_text("Camera index out of range")

            cam_name = self._cameras[index][CONFIG_CAMERA_NAME]
            if update.message:
                await update.message.reply_text(
                    f"Switched to {cam_name or f'camera {index+1}'}"
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

    async def polissa(self, update: Update, context: CallbackContext) -> None:
        """Perform Lissajous curve swing patrols."""
        self._stop_patrol_event.set()
        await asyncio.sleep(1.0)

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

        self._stop_patrol_event.clear()

        await self._fire_and_forget(
            coro=self._do_lissa_curve_patrol,
            timeout=0,
            pan_amp=pan_amp,
            pan_freq=pan_freq,
            tilt_amp=tilt_amp,
            tilt_freq=tilt_freq,
            phase_shift=phase_shift,
            step_sleep_time=step_sleep_time,
        )

    async def _do_lissa_curve_patrol(
        self,
        pan_amp: float = 1.0,
        pan_freq: float = 0.1,
        tilt_amp: float = 1.0,
        tilt_freq: float = 0.1,
        phase_shift: float = np.pi / 2,
        step_sleep_time: float = 0.1,
        pan_range: tuple = (-1.0, 1.0),
        tilt_range: tuple = (-1.0, 1.0),
    ):
        """
        Perform a Lissajous curve patrol.

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
        """
        pan_min, pan_max = pan_range
        tilt_min, tilt_max = tilt_range

        t = 0.0
        while not self._stop_patrol_event.is_set():
            t += 1.0
            x = pan_amp * np.sin(pan_freq * t + phase_shift)
            y = tilt_amp * np.sin(tilt_freq * t)

            # Scale x and y to the specified pan and tilt ranges
            x = pan_min + (x + 1) * (pan_max - pan_min) / 2
            y = tilt_min + (y + 1) * (tilt_max - tilt_min) / 2

            self.absolute_move(x, y)
            await asyncio.sleep(step_sleep_time)

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
