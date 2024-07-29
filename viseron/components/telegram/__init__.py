"""PTZ over Telegram."""

from __future__ import annotations

import asyncio
import io
import logging
import os
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

# from viseron.components.storage.models import TriggerTypes
from viseron.const import EVENT_STATE_CHANGED, VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import EVENT_RECORDER_COMPLETE
from viseron.domains.camera.recorder import EventRecorderData
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
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DETECTION_LABEL,
    DESC_SEND_MESSAGE,
    DESC_SEND_THUMBNAIL,
    DESC_SEND_VIDEO,
    DESC_TELEGRAM_BOT_TOKEN,
    DESC_TELEGRAM_CHAT_IDS,
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
                CONFIG_SEND_MESSAGE, description=DESC_SEND_MESSAGE, default=False
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
    full_config = config
    config = config[COMPONENT]

    if not full_config[CONFIG_PTZ_COMPONENT]:
        LOGGER.info("No PTZ component, won't start Telegram PTZ Controller. ")
    else:
        telegram_ptz = TelegramPTZ(vis, config)
        Thread(target=telegram_ptz.run_async).start()

    telegram_notifier = TelegramEventNotifier(vis, config)
    telegram_notifier.listen()

    vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, telegram_ptz.stop)
    return True


def lissajous_curve(amp_x, amp_y, f_x, f_y, delta, t):
    """Compute x and y values for a Lissajous curve."""
    x = amp_x * np.sin(f_x * t + delta)
    y = amp_y * np.sin(f_y * t)
    return x, y


class TelegramEventNotifier:
    """Telegram event notifier class."""

    def __init__(self, vis, config) -> None:
        self._vis = vis
        self._config = config
        self._bot_token = self._config[CONFIG_TELEGRAM_BOT_TOKEN]
        self._chat_ids = self._config[CONFIG_TELEGRAM_CHAT_IDS]
        self._bot = Bot(token=self._bot_token)
        vis.data[COMPONENT] = self

    def listen(self) -> None:
        """Listen for events to send notifications for."""

        # This doesn't work. I'm not getting the recorder complete event.
        # I do have create_event_clip set to true.
        for camera_identifier in self._config[CONFIG_CAMERAS]:
            self._vis.listen_event(
                EVENT_RECORDER_COMPLETE.format(camera_identifier=camera_identifier),
                self._recorder_complete,
            )
        self._vis.listen_event(EVENT_STATE_CHANGED, self.state_changed)

    # pylint: disable=unused-argument
    def _recorder_complete(self, event_data: Event[EventRecorderData]) -> None:
        # Never gets here?
        LOGGER.info("Recorder complete event")

    def state_changed(self, event_data: Event) -> None:
        """Viseron state change listener."""
        if (
            event_data.data.entity_id
            and event_data.data.entity_id.startswith("binary_sensor.")
            and event_data.data.entity_id.endswith("_recorder")
            and event_data.data.current_state
            and event_data.data.current_state.state == "off"
            and event_data.data.previous_state
            and event_data.data.previous_state.state == "on"
            and len(event_data.data.previous_state.attributes["objects"]) > 0
            and event_data.data.previous_state.attributes["objects"][0].label
            == self._config[CONFIG_DETECTION_LABEL]
        ):
            # bit of hacky way to get the camera name
            cam_name = event_data.data.entity_id.replace("binary_sensor.", "").replace(
                "_recorder", ""
            )
            if cam_name in self._config[CONFIG_CAMERAS]:
                LOGGER.info(
                    f"Camera {cam_name} stopped recording"
                    f"a {self._config[CONFIG_DETECTION_LABEL]}"
                    " - sending telegram notifications"
                )
                asyncio.run(self._notify_telegram(event_data))

    async def _notify_telegram(self, event_data) -> None:
        """Notify Telegram."""
        label = self._config[CONFIG_DETECTION_LABEL]
        camera_identifier = event_data.data.entity_id
        for chat_id in self._chat_ids:
            if self._config[CONFIG_SEND_THUMBNAIL]:
                file = event_data.data.previous_state.attributes["thumbnail_path"]
                if os.path.exists(file):
                    await self._bot.send_photo(
                        chat_id=chat_id,
                        photo=open(
                            event_data.data.previous_state.attributes["thumbnail_path"],
                            "rb",
                        ),
                        caption=f"{label} detected at {camera_identifier}",
                    )
            if self._config[CONFIG_SEND_VIDEO]:
                file = event_data.data.previous_state.attributes["path"]
                if os.path.exists(file):
                    await self._bot.send_video(
                        chat_id=chat_id,
                        video=open(
                            event_data.data.previous_state.attributes["path"], "rb"
                        ),
                        caption=f"{label} detected at {camera_identifier}",
                    )
            if self._config[CONFIG_SEND_MESSAGE]:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=f"{label} detected at {camera_identifier}",
                )


class TelegramPTZ:
    """PTZ class allows control of pan/tilt/zoom over Telegram."""

    def __init__(self, vis, config) -> None:
        self._vis = vis
        self._config = config
        self._bot_token = self._config[CONFIG_TELEGRAM_BOT_TOKEN]
        self._app: Application | None = None
        self._ptz: PTZ = self._vis.data[CONFIG_PTZ_COMPONENT]
        self._active_cam_ident: str = self._config[CONFIG_CAMERAS].keys()[0] | ""
        self._stop_event = asyncio.Event()
        vis.data[COMPONENT] = self

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
        self._app.add_handler(CommandHandler("toggle", self.toggle_camera))
        self._app.add_handler(CommandHandler("t", self.toggle_camera))
        self._app.add_handler(CommandHandler("stop", self.stop_patrol))
        self._app.add_handler(CommandHandler("st", self.stop_patrol))
        self._app.add_handler(CommandHandler("pos", self.get_position))
        self._app.add_handler(CommandHandler("lissa", self.lissa))
        self._app.add_handler(CallbackQueryHandler(self.callback_parser))

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
        """Stop PTZ Controller."""
        self._stop_event.set()
        LOGGER.info("Stopping Telegram PTZ Controller")

    def run_async(self):
        """Run Telegram PTZ Controller in a new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.listen())
        LOGGER.info("PTZ Controller done")

    # pylint: disable=unused-argument
    async def pan_left(self, update: Update, context: CallbackContext) -> None:
        """Pan the camera to the left."""
        self._ptz.pan_left(camera_identifier=self._active_cam_ident, step_size=0.1)

    # pylint: disable=unused-argument
    async def pan_right(self, update: Update, context: CallbackContext) -> None:
        """Pan the camera to the right."""
        self._ptz.pan_right(camera_identifier=self._active_cam_ident, step_size=0.1)

    # pylint: disable=unused-argument
    async def tilt_up(self, update: Update, context: CallbackContext) -> None:
        """Tilt the camera up."""
        self._ptz.tilt_up(camera_identifier=self._active_cam_ident, step_size=0.1)

    # pylint: disable=unused-argument
    async def tilt_down(self, update: Update, context: CallbackContext) -> None:
        """Tilt the camera down."""
        self._ptz.tilt_down(camera_identifier=self._active_cam_ident, step_size=0.1)

    # pylint: disable=unused-argument
    async def zoom_out(self, update: Update, context: CallbackContext) -> None:
        """Zoom the camera out."""
        self._ptz.zoom_out(camera_identifier=self._active_cam_ident, step_size=0.1)

    # pylint: disable=unused-argument
    async def zoom_in(self, update: Update, context: CallbackContext) -> None:
        """Zoom the camera in."""
        self._ptz.zoom_in(camera_identifier=self._active_cam_ident, step_size=0.1)

    # pylint: disable=unused-argument
    async def list_cams(self, update: Update, context: CallbackContext) -> None:
        """
        List all available cameras.

        The user can select a camera to switch to by clicking on the camera name.
        """
        try:
            keyboard = []
            cameras = self._ptz.get_registered_cameras()
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
                await update.message.reply_text(
                    "Select a camera",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
        except TelegramError as e:
            LOGGER.error(e)

    # pylint: disable=unused-argument
    async def callback_parser(self, update: Update, context: CallbackContext) -> None:
        """Parse the callback data from the inline keyboard."""
        query = update.callback_query
        if query:
            await query.answer(read_timeout=30)
            self._active_cam_ident = str(query.data)
            await query.edit_message_text(text=f"Switched to camera {query.data}")

    # pylint: disable=unused-argument
    async def get_position(self, update: Update, context: CallbackContext) -> None:
        """Get the current position of the camera."""
        x, y = self._ptz.get_position(self._active_cam_ident)
        if update.message:
            await update.message.reply_text(f"Position: {x}, {y}")

    async def patrol(self, update: Update, context: CallbackContext) -> None:
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
        duration = 60 * 60 * 24
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
    async def stop_patrol(self, update: Update, context: CallbackContext) -> None:
        """Stop the patrol."""
        self._ptz.stop_patrol(self._active_cam_ident)

    async def lissa(self, update: Update, context: CallbackContext) -> None:
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

    async def record(self, update: Update, context: CallbackContext) -> None:
        """
        Record a video from the camera.

        @param duration: The duration of the recording in seconds

        Parameters are passed through the Telegram message e.g.:

        /record 60

        This will record a video for 60 seconds and return it.

        This doesn't work currently. Maybe I should start recorder, stop and and then
        listen for a RECORDING_COMPLETE event or some such? I could return from this
        function immediately and come back asynchronously when the recording is done.

        The recorder also records for a certain configured period, how do I extend it?
        """
        if update.message:
            await update.message.reply_text(
                "This functionality isn't implemented yet :("
            )
        # duration = 5
        # if context.args and len(context.args) > 0:
        #     duration = int(context.args[0])
        # cam: AbstractCamera = self._ptz.get_camera(self._active_cam_ident)
        # if cam.is_recording:
        #     await update.message.reply_text("Camera is already recording.")
        #     return
        # cam.start_recorder(
        #     shared_frame=cam.current_frame,
        #     objects_in_fov=[],
        #     trigger_type=TriggerTypes.OBJECT, # MANUAL?
        # )
        # await asyncio.sleep(duration)
        # cam.stop_recorder()
        # recording = cam.recorder.get_latest_recording()
        # if recording:
        #     date_key = next(iter(recording))
        #     recording_data = recording[date_key]
        #     thumbnail_path = next(iter(recording_data.values()))["thumbnail_path"]
        #     await update.message.reply_photo(photo=open(thumbnail_path, "rb"))
        # else:
        #     await update.message.reply_text("No recording found.")

    async def toggle_camera(self, update: Update, context: CallbackContext) -> None:
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
