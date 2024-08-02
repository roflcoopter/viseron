"""PTZ interface."""

from __future__ import annotations

import asyncio
import logging
from threading import Thread
from typing import TYPE_CHECKING

import numpy as np
import voluptuous as vol
from onvif import ONVIFCamera, ONVIFError, ONVIFService

from viseron.const import EVENT_DOMAIN_REGISTERED, VISERON_SIGNAL_STOPPING
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.helpers import escape_string
from viseron.helpers.logs import SensitiveInformationFilter
from viseron.helpers.validators import CameraIdentifier

from .const import (
    COMPONENT,
    CONFIG_CAMERA_FULL_SWING_MAX_PAN,
    CONFIG_CAMERA_FULL_SWING_MIN_PAN,
    CONFIG_CAMERA_PASSWORD,
    CONFIG_CAMERA_PORT,
    CONFIG_CAMERA_USERNAME,
    CONFIG_CAMERAS,
    CONFIG_HOST,
    CONFIG_PRESET_NAME,
    CONFIG_PRESET_ON_STARTUP,
    CONFIG_PRESET_PAN,
    CONFIG_PRESET_TILT,
    CONFIG_PRESET_ZOOM,
    CONFIG_PTZ_PRESETS,
    DESC_CAMERA_FULL_SWING_MAX_PAN,
    DESC_CAMERA_FULL_SWING_MIN_PAN,
    DESC_CAMERA_PASSWORD,
    DESC_CAMERA_PORT,
    DESC_CAMERA_USERNAME,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_PRESET_NAME,
    DESC_PRESET_ON_STARTUP,
    DESC_PRESET_PAN,
    DESC_PRESET_TILT,
    DESC_PRESET_ZOOM,
    DESC_PTZ_PRESETS,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron

LOGGER = logging.getLogger(__name__)

PRESET = vol.Schema(
    {
        vol.Required(CONFIG_PRESET_NAME, description=DESC_PRESET_NAME): str,
        vol.Required(CONFIG_PRESET_PAN, description=DESC_PRESET_PAN): float,
        vol.Required(CONFIG_PRESET_TILT, description=DESC_PRESET_TILT): float,
        vol.Optional(CONFIG_PRESET_ZOOM, description=DESC_PRESET_ZOOM): float,
        vol.Optional(
            CONFIG_PRESET_ON_STARTUP, description=DESC_PRESET_ON_STARTUP, default=False
        ): bool,
    }
)

CAMERA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_CAMERA_PORT, description=DESC_CAMERA_PORT, default=80): int,
        vol.Required(CONFIG_CAMERA_USERNAME, description=DESC_CAMERA_USERNAME): str,
        vol.Required(CONFIG_CAMERA_PASSWORD, description=DESC_CAMERA_PASSWORD): str,
        vol.Optional(
            CONFIG_CAMERA_FULL_SWING_MIN_PAN,
            description=DESC_CAMERA_FULL_SWING_MIN_PAN,
        ): float,
        vol.Optional(
            CONFIG_CAMERA_FULL_SWING_MAX_PAN,
            description=DESC_CAMERA_FULL_SWING_MAX_PAN,
        ): float,
        vol.Optional(CONFIG_PTZ_PRESETS, description=DESC_PTZ_PRESETS): [PRESET],
    }
)

COMPONENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
            CameraIdentifier(): CAMERA_SCHEMA
        },
    }
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Required(COMPONENT, description=DESC_COMPONENT): COMPONENT_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config) -> bool:
    """Set up the ptz component."""
    ptz = PTZ(vis, config[COMPONENT])
    Thread(
        target=ptz.run,
        name="ptz",
    ).start()
    return True


class PTZ:
    """PTZ class allows control of pan/tilt/zoom (and other stuff) over Telegram."""

    def __init__(self, vis: Viseron, config) -> None:
        self._vis = vis
        self._config = config
        for cam_name in self._config[CONFIG_CAMERAS]:
            camera = self._config[CONFIG_CAMERAS][cam_name]
            if camera[CONFIG_CAMERA_PASSWORD]:
                SensitiveInformationFilter.add_sensitive_string(
                    camera[CONFIG_CAMERA_PASSWORD]
                )
                SensitiveInformationFilter.add_sensitive_string(
                    escape_string(camera[CONFIG_CAMERA_PASSWORD])
                )
        self._cameras: dict[str, AbstractCamera] = {}
        self._onvif_cameras: dict[str, ONVIFCamera] = {}
        self._ptz_services: dict[str, ONVIFService] = {}
        self._ptz_tokens: dict[str, str] = {}
        self._stop_patrol_events: dict[str, asyncio.Event] = {}
        self._register_lock: asyncio.Lock = asyncio.Lock()
        self._stop_event: asyncio.Event = asyncio.Event()
        vis.data[COMPONENT] = self

    def initialize(self):
        """Initialize PTZ Controller."""
        self._vis.register_signal_handler(VISERON_SIGNAL_STOPPING, self.shutdown)
        self._vis.listen_event(
            EVENT_DOMAIN_REGISTERED.format(domain=CAMERA_DOMAIN),
            self._camera_registered,
        )

    def run(self):
        """Run PTZ Controller."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._run())
        LOGGER.info("PTZ Controller done")

    async def _run(self):
        """Run PTZ Controller."""
        self.initialize()
        while not self._stop_event.is_set():
            await asyncio.sleep(0.1)

    def shutdown(self):
        """Shutdown PTZ Controller."""
        for event in self._stop_patrol_events.values():
            event.set()
        self._stop_event.set()

    def _camera_registered(self, event: Event[AbstractCamera]) -> None:
        camera: AbstractCamera = event.data
        if camera.identifier in self._config[CONFIG_CAMERAS]:
            self._cameras.update({camera.identifier: camera})
            config = self._config[CONFIG_CAMERAS][camera.identifier]
            onvif_camera = ONVIFCamera(
                camera.config[CONFIG_HOST],
                config[CONFIG_CAMERA_PORT],
                config[CONFIG_CAMERA_USERNAME],
                config[CONFIG_CAMERA_PASSWORD],
            )
            self._onvif_cameras.update({camera.identifier: onvif_camera})
            self._ptz_services.update(
                {camera.identifier: onvif_camera.create_ptz_service()}
            )
            media_service = onvif_camera.create_media_service()
            self._ptz_tokens.update(
                {camera.identifier: media_service.GetProfiles()[0].token}
            )
            self._stop_patrol_events.update({camera.identifier: asyncio.Event()})
            if CONFIG_PTZ_PRESETS in config:
                for preset in config[CONFIG_PTZ_PRESETS]:
                    if preset[CONFIG_PRESET_ON_STARTUP]:
                        self.move_to_preset(
                            camera.identifier, preset[CONFIG_PRESET_NAME]
                        )

    def get_registered_cameras(self) -> dict[str, AbstractCamera]:
        """Get the registered cameras."""
        return self._cameras

    def get_camera(self, camera_identifier: str) -> AbstractCamera | None:
        """Get a camera by identifier."""
        return self._cameras.get(camera_identifier)

    async def patrol(
        self,
        camera_identifier: str,
        duration: int = 60,
        sleep_after_swing: int = 6,
        step_size: float = 0.1,
        step_sleep_time: float = 0.1,
    ) -> None:
        """Perform a patrol of the camera."""
        stop_event = self._stop_patrol_events.get(camera_identifier)
        if stop_event is not None:
            stop_event.clear()
        await self._fire_and_forget(
            self._do_patrol,
            duration,
            camera_identifier=camera_identifier,
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

    async def _do_patrol(
        self,
        camera_identifier: str,
        step_size: float = 0.1,
        step_sleep_time: float = 0.1,
        sleep_after_swing=6,
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

            ptz_service = self._ptz_services.get(camera_identifier)
            if ptz_service is None:
                LOGGER.error(f"No PTZ service for camera {camera_identifier}")
                return

            # Get and store starting position
            status = ptz_service.GetStatus(
                {"ProfileToken": self._ptz_tokens.get(camera_identifier)}
            )
            if status is None:
                LOGGER.warning("Cannot determine starting position")
                initial_pan = 0.0
                initial_tilt = 0.0
            else:
                initial_pan = status.Position.PanTilt.x
                initial_tilt = status.Position.PanTilt.y
                LOGGER.debug(
                    f"Camera position at start: x: {initial_pan}, y: {initial_tilt}"
                )

            # Get the camera's FOV limits, if any.
            cam = self._cameras.get(camera_identifier)
            if cam is None:
                LOGGER.error(f"No camera found for {camera_identifier}")
                return

            min_pan = cam.config.get(CONFIG_CAMERA_FULL_SWING_MIN_PAN)
            max_pan = cam.config.get(CONFIG_CAMERA_FULL_SWING_MAX_PAN)

            # Decide which direction to start swinging based on the distance to the
            # camera's FOV limits, left if closer to min_pan, right if closer to max_pan
            distance_to_min = initial_pan - min_pan if min_pan else 0
            distance_to_max = max_pan - initial_pan if max_pan else 0
            left = distance_to_min > distance_to_max

            # Swing back and forth until stopped
            stop_patrol_event = self._stop_patrol_events.get(camera_identifier)
            if stop_patrol_event is None:
                stop_patrol_event = asyncio.Event()
                self._stop_patrol_events.update({camera_identifier: stop_patrol_event})

            while not stop_patrol_event.is_set():
                await self.full_swing(
                    camera_identifier=camera_identifier,
                    is_left=left,
                    step_size=step_size,
                    step_sleep_time=step_sleep_time,
                    min_pan=min_pan,
                    max_pan=max_pan,
                )
                if stop_patrol_event.is_set():
                    break
                await asyncio.sleep(sleep_after_swing)
                left = not left

        finally:
            # Move back to the initial position
            self.absolute_move(
                camera_identifier=camera_identifier, pan=initial_pan, tilt=initial_tilt
            )

    def stop_patrol(self, camera_identifier: str) -> None:
        """Stop the patrol."""
        event = self._stop_patrol_events.get(camera_identifier)
        if event:
            event.set()

    async def lissajous_curve_patrol(
        self,
        camera_identifier: str,
        pan_amp: float = 1.0,
        pan_freq: float = 0.1,
        tilt_amp: float = 1.0,
        tilt_freq: float = 0.1,
        phase_shift: float = np.pi / 2,
        step_sleep_time: float = 0.1,
    ):
        """Perform a Lissajous curve patrol."""

        stop_patrol_event = self._stop_patrol_events.get(camera_identifier)
        if stop_patrol_event is None:
            LOGGER.error(f"No patrol stop event for camera {camera_identifier}")
            return False

        # stop currently running patrol
        if not stop_patrol_event.is_set():
            stop_patrol_event.set()
            await asyncio.sleep(2.0)
            stop_patrol_event.clear()

        # start a new patrol
        await self._fire_and_forget(
            coro=self._do_lissa_curve_patrol,
            timeout=0,
            camera_identifier=camera_identifier,
            pan_amp=pan_amp,
            pan_freq=pan_freq,
            tilt_amp=tilt_amp,
            tilt_freq=tilt_freq,
            phase_shift=phase_shift,
            step_sleep_time=step_sleep_time,
        )

    async def _do_lissa_curve_patrol(
        self,
        camera_identifier: str,
        pan_amp: float = 1.0,
        pan_freq: float = 0.1,
        tilt_amp: float = 1.0,
        tilt_freq: float = 0.1,
        phase_shift: float = np.pi / 2,
        step_sleep_time: float = 0.1,
        pan_range: tuple = (-1.0, 1.0),
        tilt_range: tuple = (-1.0, 1.0),
    ):
        """Perform a Lissajous curve patrol."""
        stop_patrol_event = self._stop_patrol_events.get(camera_identifier)
        if stop_patrol_event is None:
            stop_patrol_event = asyncio.Event()
            self._stop_patrol_events.update({camera_identifier: stop_patrol_event})

        pan_min, pan_max = pan_range
        tilt_min, tilt_max = tilt_range

        t = 0.0
        while not stop_patrol_event.is_set():
            t += 1.0
            x = pan_amp * np.sin(pan_freq * t + phase_shift)
            y = tilt_amp * np.sin(tilt_freq * t)

            # Scale x and y to the specified pan and tilt ranges
            x = pan_min + (x + 1) * (pan_max - pan_min) / 2
            y = tilt_min + (y + 1) * (tilt_max - tilt_min) / 2

            await self.absolute_move_wait_complete(
                camera_identifier=camera_identifier, pan=x, tilt=y
            )
            await asyncio.sleep(step_sleep_time)

    async def full_swing(
        self,
        camera_identifier: str,
        is_left: bool = True,
        step_size: float = 0.1,
        step_sleep_time: float = 0.1,
        min_pan: float | None = None,
        max_pan: float | None = None,
    ):
        """Perform a full swing in the pan direction.

        @param is_left: True if the swing is to the left, False if to the right
        @param step_size: The size of each move step
        @param sleep_time: Time to sleep between each move step
        @param min_pan: Minimum pan value to stop at, meant to be used to avoid
          going beyond the camera's limits or field of view
        @param max_pan: Maximum pan value to stop at

        """
        ptz_service = self._ptz_services.get(camera_identifier)
        if ptz_service is None:
            LOGGER.error(f"No PTZ service for camera {camera_identifier}")
            return

        cur_pan, _ = self.get_position(camera_identifier)
        # Get and store starting position
        LOGGER.debug(f"Fullswing start: pan: {cur_pan}, min: {min_pan}, max: {max_pan}")

        move_step = -abs(step_size) if is_left else abs(step_size)

        # Do not move beyond the camera's FOV bounds
        if is_left:
            if min_pan is not None and cur_pan + move_step <= min_pan:
                return
        else:
            if max_pan is not None and cur_pan + move_step >= max_pan:
                return

        # Move while not stopped or stopped by the camera's FOV or hardware bounds
        # Unsure how this will react to 360 (or more?) degree cameras
        stop_patrol_event = self._stop_patrol_events.get(camera_identifier)
        if stop_patrol_event is None:
            stop_patrol_event = asyncio.Event()
            self._stop_patrol_events.update({camera_identifier: stop_patrol_event})

        while (
            self.relative_move(
                camera_identifier=camera_identifier, pan=move_step, tilt=0.0
            )
            and not stop_patrol_event.is_set()
        ):
            await asyncio.sleep(step_sleep_time)
            cur_pan, _ = self.get_position(camera_identifier)
            LOGGER.debug(
                f"Fullswing moved to: pan: {cur_pan}, min: {min_pan}, max: {max_pan}"
            )
            if min_pan is not None and cur_pan <= min_pan:
                break
            if max_pan is not None and cur_pan >= max_pan:
                break

        LOGGER.debug(f"Fullswing end: pan: {cur_pan}, min: {min_pan}, max: {max_pan}")

    def relative_move(self, camera_identifier: str, pan: float, tilt: float) -> bool:
        """
        Move the camera relative to its current position.

        @param x: The relative x position to move to
        @param y: The relative y position to move to
        @return: True if the move was successful, False otherwise
        """
        ptz_service = self._ptz_services.get(camera_identifier)
        if ptz_service is None:
            LOGGER.error(f"No PTZ service for camera {camera_identifier}")
            return False

        try:
            ptz_service.RelativeMove(
                {
                    "ProfileToken": self._ptz_tokens.get(camera_identifier),
                    "Translation": {
                        "PanTilt": {"x": pan, "y": tilt},
                        "Zoom": {"x": 0.0},
                    },
                }
            )
            return True
        except ONVIFError as e:
            LOGGER.warning(f"ONVIF error in RelativeMove (usually harmless): {e}")
            return False

    def zoom(self, camera_identifier: str, zoom: float = 0.1) -> bool:
        """Zoom the camera in our out."""
        ptz_service = self._ptz_services.get(camera_identifier)
        if ptz_service is None:
            LOGGER.error(f"No PTZ service for camera {camera_identifier}")
            return False

        try:
            ptz_service.RelativeMove(
                {
                    "ProfileToken": self._ptz_tokens.get(camera_identifier),
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
            LOGGER.warning(f"ONVIF error in Zoom (usually harmless): {e}")
            return False

    def absolute_move(self, camera_identifier: str, pan: float, tilt: float) -> bool:
        """Move the camera to an absolute position."""
        ptz_service = self._ptz_services.get(camera_identifier)
        if ptz_service is None:
            LOGGER.error(f"No PTZ service for camera {camera_identifier}")
            return False
        try:
            ptz_service.AbsoluteMove(
                {
                    "ProfileToken": self._ptz_tokens.get(camera_identifier),
                    "Position": {
                        "PanTilt": {"x": pan, "y": tilt},
                    },
                }
            )
            return True
        except ONVIFError as e:
            LOGGER.warning(f"ONVIF error in AbsoluteMove (usually harmless): {e}")
            return False

    async def absolute_move_wait_complete(
        self, camera_identifier: str, pan: float, tilt: float, timeout: float = 30.0
    ) -> bool:
        """Move the camera to an absolute position and wait for the move to complete."""
        if self.absolute_move(camera_identifier=camera_identifier, pan=pan, tilt=tilt):
            # get the camera position and wait until it reaches the desired position to
            # a tolerance of 0.005, or until the timeout is reached
            tolerance = 0.005
            start_time = asyncio.get_event_loop().time()
            while (
                abs(self.get_position(camera_identifier)[0] - pan) > tolerance
                or abs(self.get_position(camera_identifier)[1] - tilt) > tolerance
            ) and (asyncio.get_event_loop().time() - start_time < timeout):
                await asyncio.sleep(0.1)
            LOGGER.info(
                "Position at end of abs move and wait (requested: %s): %s",
                (pan, tilt),
                self.get_position(camera_identifier),
            )
            return True
        return False

    async def continuous_move(
        self,
        camera_identifier: str,
        x_velocity: float,
        y_velocity: float,
        seconds: float,
    ):
        """Move the camera continuously for a set amount of time."""
        ptz_service = self._ptz_services.get(camera_identifier)
        if ptz_service is None:
            LOGGER.error(f"No PTZ service for camera {camera_identifier}")
            return False
        try:
            ptz_service.ContinuousMove(
                {
                    "ProfileToken": self._ptz_tokens.get(camera_identifier),
                    "Velocity": {
                        "PanTilt": {"x": x_velocity, "y": y_velocity},
                        "Zoom": {"x": 0.0},
                    },
                }
            )
            await asyncio.sleep(seconds)
            ptz_service.Stop({"ProfileToken": self._ptz_tokens.get(camera_identifier)})
        except ONVIFError as e:
            LOGGER.warning(f"ONVIF error in ContinuousMove (usually harmless): {e}")

    def pan_left(self, camera_identifier: str, step_size: float = 0.1) -> bool:
        """Pan the camera to the left."""
        return self.relative_move(
            camera_identifier=camera_identifier, pan=-step_size, tilt=0.0
        )

    def pan_right(self, camera_identifier: str, step_size: float = 0.1) -> bool:
        """Pan the camera to the right."""
        return self.relative_move(
            camera_identifier=camera_identifier, pan=step_size, tilt=0.0
        )

    def tilt_up(self, camera_identifier: str, step_size: float = 0.1) -> bool:
        """Tilt the camera up."""
        return self.relative_move(
            camera_identifier=camera_identifier, pan=0.0, tilt=step_size
        )

    def tilt_down(self, camera_identifier: str, step_size: float = 0.1) -> bool:
        """Tilt the camera down."""
        return self.relative_move(
            camera_identifier=camera_identifier, pan=0.0, tilt=-step_size
        )

    def zoom_out(self, camera_identifier: str, step_size: float = 0.1) -> bool:
        """Zoom the camera out."""
        return self.zoom(camera_identifier=camera_identifier, zoom=-step_size)

    def zoom_in(self, camera_identifier: str, step_size: float = 0.1) -> bool:
        """Zoom the camera in."""
        return self.zoom(camera_identifier=camera_identifier, zoom=step_size)

    def get_position(self, camera_identifier: str) -> tuple[float, float]:
        """Get the current position of the camera."""
        ptz_service = self._ptz_services.get(camera_identifier)
        if ptz_service is None:
            LOGGER.error(f"No PTZ service for camera {camera_identifier}")
            return 0.0, 0.0
        try:
            status = ptz_service.GetStatus(
                {"ProfileToken": self._ptz_tokens.get(camera_identifier)}
            )
            return status.Position.PanTilt.x, status.Position.PanTilt.y
        except ONVIFError as e:
            LOGGER.warning(f"ONVIF error in GetStatus (usually harmless): {e}")
            return -255.0, -255.0

    def get_presets(self, camera_identifier: str) -> list[str]:
        """Get the available presets for the camera."""
        presets = self._config[CONFIG_CAMERAS][camera_identifier][CONFIG_PTZ_PRESETS]
        return list({preset[CONFIG_PRESET_NAME] for preset in presets})

    def move_to_preset(self, camera_identifier: str, preset_name: str) -> bool:
        """Move the camera to a preset position."""
        if CONFIG_PTZ_PRESETS not in self._config[CONFIG_CAMERAS][camera_identifier]:
            LOGGER.error(f"No PTZ presets for camera {camera_identifier}")
            return False

        if not any(
            preset[CONFIG_PRESET_NAME] == preset_name
            for preset in self._config[CONFIG_CAMERAS][camera_identifier][
                CONFIG_PTZ_PRESETS
            ]
        ):
            LOGGER.error(
                f"Preset {preset_name} not found for camera {camera_identifier}"
            )
            return False

        presets = self._config[CONFIG_CAMERAS][camera_identifier][CONFIG_PTZ_PRESETS]
        for preset in presets:
            if preset[CONFIG_PRESET_NAME] == preset_name:
                self.absolute_move(
                    camera_identifier=camera_identifier,
                    pan=preset[CONFIG_PRESET_PAN],
                    tilt=preset[CONFIG_PRESET_TILT],
                )
                if CONFIG_PRESET_ZOOM in preset:
                    self.zoom(
                        camera_identifier=camera_identifier,
                        zoom=preset[CONFIG_PRESET_ZOOM],
                    )
        return True

    async def move_to_preset_wait_complete(
        self, camera_identifier: str, preset_name: str
    ) -> bool:
        """Move the camera to a preset position."""
        if CONFIG_PTZ_PRESETS not in self._config[CONFIG_CAMERAS][camera_identifier]:
            LOGGER.error(f"No PTZ presets for camera {camera_identifier}")
            return False

        presets = self._config[CONFIG_CAMERAS][camera_identifier][CONFIG_PTZ_PRESETS]

        if not presets:
            LOGGER.error(f"No PTZ presets for camera {camera_identifier}")
            return False

        if not any(preset[CONFIG_PRESET_NAME] == preset_name for preset in presets):
            LOGGER.error(
                f"Preset {preset_name} not found for camera {camera_identifier}"
            )
            return False

        for preset in presets:
            if preset[CONFIG_PRESET_NAME] == preset_name:
                await self.absolute_move_wait_complete(
                    camera_identifier=camera_identifier,
                    pan=preset[CONFIG_PRESET_PAN],
                    tilt=preset[CONFIG_PRESET_TILT],
                )
                if CONFIG_PRESET_ZOOM in preset:
                    self.zoom(
                        camera_identifier=camera_identifier,
                        zoom=preset[CONFIG_PRESET_ZOOM],
                    )
        return True
