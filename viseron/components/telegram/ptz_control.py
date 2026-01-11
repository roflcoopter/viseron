"""Telegram PTZ component."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING

import cv2
import numpy as np
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, CommandHandler

from viseron.components.onvif import ONVIF
from viseron.components.onvif.const import COMPONENT as ONVIF_COMPONENT
from viseron.components.telegram.utils import limit_user_access

from .const import COMPONENT

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.telegram import TelegramEventNotifier

LOGGER = logging.getLogger(__name__)


def lissajous_curve(amp_x, amp_y, f_x, f_y, delta, t):
    """Compute x and y values for a Lissajous curve."""
    x = amp_x * np.sin(f_x * t + delta)
    y = amp_y * np.sin(f_y * t)
    return x, y


class TelegramPTZ:
    """TelegramPTZ class allows control of p/t/z (and other stuff) over Telegram."""

    def __init__(self, vis: Viseron, config, telegram: TelegramEventNotifier) -> None:
        self._vis = vis
        self._config = config
        self._telegram = telegram
        self._onvif: ONVIF = self._vis.data[ONVIF_COMPONENT]
        self._stop_event = asyncio.Event()
        vis.data[COMPONENT] = self

    @property
    def _ptz_service(self):
        """Get PTZ service for active camera."""
        return self._onvif.get_ptz_service(self._telegram.active_camera_identifier)

    async def _listen(self) -> None:
        """Start listening for commands from Telegram."""
        self._telegram.app.add_handler(CommandHandler("home", self._home))
        self._telegram.app.add_handler(CommandHandler("h", self._home))
        self._telegram.app.add_handler(CommandHandler("left", self._pan_left))
        self._telegram.app.add_handler(CommandHandler("l", self._pan_left))
        self._telegram.app.add_handler(CommandHandler("right", self._pan_right))
        self._telegram.app.add_handler(CommandHandler("r", self._pan_right))
        self._telegram.app.add_handler(CommandHandler("up", self._tilt_up))
        self._telegram.app.add_handler(CommandHandler("u", self._tilt_up))
        self._telegram.app.add_handler(CommandHandler("down", self._tilt_down))
        self._telegram.app.add_handler(CommandHandler("d", self._tilt_down))
        self._telegram.app.add_handler(CommandHandler("zo", self._zoom_out))
        self._telegram.app.add_handler(CommandHandler("o", self._zoom_out))
        self._telegram.app.add_handler(CommandHandler("zi", self._zoom_in))
        self._telegram.app.add_handler(CommandHandler("i", self._zoom_in))
        self._telegram.app.add_handler(CommandHandler("pos", self._get_position))
        self._telegram.app.add_handler(CommandHandler("preset", self._preset))
        self._telegram.app.add_handler(CommandHandler("pr", self._preset))
        self._telegram.app.add_handler(CommandHandler("repeat", self._repeat_preset))
        self._telegram.app.add_handler(CommandHandler("patrol", self._patrol))
        self._telegram.app.add_handler(CommandHandler("p", self._patrol))
        self._telegram.app.add_handler(CommandHandler("lissa", self._lissa))
        self._telegram.app.add_handler(CommandHandler("stop", self._stop_patrol))
        self._telegram.app.add_handler(CommandHandler("st", self._stop_patrol))

        while not self._stop_event.is_set():
            await asyncio.sleep(1)

        LOGGER.info("TelegramPTZ Controller stopped")

    def stop(self) -> None:
        """Stop TelegramPTZ Controller."""
        self._stop_event.set()
        LOGGER.info("Stopping TelegramPTZ Controller")

    def run_async(self):
        """Run TelegramPTZ Controller in a new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._listen())
        LOGGER.info("TelegramPTZ Controller done")

    async def _inform(
        self, update: Update, operation: str, status: bool | None
    ) -> None:
        """Inform the user with a message."""
        if update.message:
            if status:
                message_status = "executed"
            elif status is None:
                message_status = "started"
            else:
                message_status = "failed"
            message = (
                f"<b>{operation.upper().replace('_', ' ')}</b> {message_status} for "
                f"{self._telegram.active_camera_identifier}"
            )
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
            )

    # pylint: disable=unused-argument
    @limit_user_access
    async def _home(self, update: Update, context: CallbackContext) -> None:
        """Move the camera to its home position."""

        status = (
            await self._ptz_service.go_home_position() if self._ptz_service else False
        )
        await self._inform(update, "home", status)

    # pylint: disable=unused-argument
    @limit_user_access
    async def _pan_left(self, update: Update, context: CallbackContext) -> None:
        """
        Pan the camera to the left.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args:
            step_size = float(context.args[0])

        status = (
            await self._ptz_service.pan_left(step_size=step_size)
            if self._ptz_service
            else False
        )
        await self._inform(update, "pan_left", status)

    # pylint: disable=unused-argument
    @limit_user_access
    async def _pan_right(self, update: Update, context: CallbackContext) -> None:
        """
        Pan the camera to the right.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args:
            step_size = float(context.args[0])

        status = (
            await self._ptz_service.pan_right(step_size=step_size)
            if self._ptz_service
            else False
        )
        await self._inform(update, "pan_right", status)

    # pylint: disable=unused-argument
    @limit_user_access
    async def _tilt_up(self, update: Update, context: CallbackContext) -> None:
        """
        Tilt the camera up.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args:
            step_size = float(context.args[0])

        status = (
            await self._ptz_service.tilt_up(step_size=step_size)
            if self._ptz_service
            else False
        )
        await self._inform(update, "tilt_up", status)

    # pylint: disable=unused-argument
    @limit_user_access
    async def _tilt_down(self, update: Update, context: CallbackContext) -> None:
        """
        Tilt the camera down.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args:
            step_size = float(context.args[0])

        status = (
            await self._ptz_service.tilt_down(step_size=step_size)
            if self._ptz_service
            else False
        )
        await self._inform(update, "tilt_down", status)

    # pylint: disable=unused-argument
    @limit_user_access
    async def _zoom_out(self, update: Update, context: CallbackContext) -> None:
        """
        Zoom the camera out.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args:
            step_size = float(context.args[0])

        status = (
            await self._ptz_service.zoom_out(step_size=step_size)
            if self._ptz_service
            else False
        )
        await self._inform(update, "zoom_out", status)

    # pylint: disable=unused-argument
    @limit_user_access
    async def _zoom_in(self, update: Update, context: CallbackContext) -> None:
        """
        Zoom the camera in.

        @param step_size: The size of the move step, usually between -1.0 and 1.0.
        """
        step_size = 0.1
        if context.args:
            step_size = float(context.args[0])

        status = (
            await self._ptz_service.zoom_in(step_size=step_size)
            if self._ptz_service
            else False
        )
        await self._inform(update, "zoom_in", status)

    @limit_user_access
    async def _get_position(self, update: Update, context: CallbackContext) -> None:
        """Get the current (PTZ) position of the camera."""
        x, y, z = (
            await self._ptz_service.get_position()
            if self._ptz_service
            else (False, False, False)
        )
        if x is False or y is False or z is False:
            if update.message:
                await update.message.reply_text(
                    f"Could not get position for "
                    f"{self._telegram.active_camera_identifier}"
                )
            return
        if update.message:
            await update.message.reply_text(
                f"{self._telegram.active_camera_identifier} position:\n"
                f"PanTilt = x : {x}, y : {y}\nZoom = x : {z}"
            )

    @limit_user_access
    async def _patrol(self, update: Update, context: CallbackContext) -> None:
        """
        Swings the camera from left to right and back.

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
        if context.args:
            duration = int(context.args[0])
        if context.args and len(context.args) > 1:
            sleep_after_swing = int(context.args[1])
        if context.args and len(context.args) > 2:
            step_size = float(context.args[2])
        if context.args and len(context.args) > 3:
            step_sleep_time = float(context.args[3])

        status = (
            await self._ptz_service.patrol(
                duration=duration,
                sleep_after_swing=sleep_after_swing,
                step_size=step_size,
                step_sleep_time=step_sleep_time,
            )
            if self._ptz_service
            else False
        )
        await self._inform(update, "patrol", status)

    # pylint: disable=unused-argument
    @limit_user_access
    async def _stop_patrol(self, update: Update, context: CallbackContext) -> None:
        """Stop the patrol."""
        status = await self._ptz_service.stop_patrol() if self._ptz_service else False
        await self._inform(update, "stop_patrol", status)

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

        if context.args:
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

        status = (
            await self._ptz_service.lissajous_curve_patrol(
                pan_amp=pan_amp,
                pan_freq=pan_freq,
                tilt_amp=tilt_amp,
                tilt_freq=tilt_freq,
                phase_shift=phase_shift,
                step_sleep_time=step_sleep_time,
            )
            if self._ptz_service
            else False
        )

        await self._inform(update, "lissa_patrol", status)

    @limit_user_access
    async def _preset(self, update: Update, context: CallbackContext) -> None:
        """
        Change the camera to a preset position.

        Use /preset <name> to move the camera to a preset position.
        Use /preset list to get a list of available presets.
        """
        name = "list" if not context.args else context.args[0]
        if name == "list":
            if not self._ptz_service:
                if update.message:
                    await update.message.reply_text("No PTZ service available.")
                return
            config_presets = self._ptz_service.get_configured_presets()
            config_preset_cmds = "\n".join(
                f"/preset {preset}" for preset in config_presets
            )
            presets = await self._ptz_service.get_presets()
            preset_cmds = "\n".join(
                f"/preset {preset.Name or preset.token}" for preset in presets
            )
            all_presets = config_preset_cmds + "\n" + preset_cmds
            if update.message:
                await update.message.reply_text(f"Available presets:\n{all_presets}")
                return

        could_complete = await self._ptz_service.move_to_preset(preset_name=name)
        if update.message:
            if could_complete:
                await update.message.reply_text(
                    f"Moved to preset <b>{name}</b>", parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    f"Failed to move to preset <b>{name}</b>", parse_mode=ParseMode.HTML
                )

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
            if not self._ptz_service:
                if update.message:
                    await update.message.reply_text("No PTZ service available.")
                return
            config_presets = self._ptz_service.get_configured_presets()
            config_preset_cmds = "\n".join(
                f"/preset {preset}" for preset in config_presets
            )
            presets = await self._ptz_service.get_presets()
            preset_cmds = "\n".join(
                f"/preset {preset.Name or preset.token}" for preset in presets
            )
            all_presets = config_preset_cmds + "\n" + preset_cmds
            if update.message:
                await update.message.reply_text(f"Available presets:\n{all_presets}")
                return

        repeat_count = 5
        if context.args and len(context.args) > 1:
            repeat_count = int(context.args[1])

        async def run_presets_sequentially():
            for _ in range(repeat_count):
                await self._ptz_service.move_to_preset(preset_name=name)

        # Schedule the task to run in the background
        asyncio.create_task(run_presets_sequentially())

        # Return immediately
        if update.message:
            await update.message.reply_text(f"Started repeating preset '{name}'")
