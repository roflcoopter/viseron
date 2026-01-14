"""PTZ service management for ONVIF component."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from onvif import ONVIFClient

from .const import (
    CONFIG_PTZ_HOME_POSITION,
    CONFIG_PTZ_MAX_PAN,
    CONFIG_PTZ_MAX_TILT,
    CONFIG_PTZ_MAX_ZOOM,
    CONFIG_PTZ_MIN_PAN,
    CONFIG_PTZ_MIN_TILT,
    CONFIG_PTZ_MIN_ZOOM,
    CONFIG_PTZ_PRESET_NAME,
    CONFIG_PTZ_PRESET_ON_STARTUP,
    CONFIG_PTZ_PRESET_PAN,
    CONFIG_PTZ_PRESET_TILT,
    CONFIG_PTZ_PRESET_ZOOM,
    CONFIG_PTZ_PRESETS,
    CONFIG_PTZ_REVERSE_PAN,
    CONFIG_PTZ_REVERSE_TILT,
)
from .utils import operation

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


class PTZ:
    """Class for managing PTZ operations for an ONVIF camera."""

    def __init__(
        self,
        camera: AbstractCamera,
        client: ONVIFClient,
        config: dict[str, Any],
        auto_config: bool = True,
        media_service: Any = None,
    ) -> None:
        self._camera = camera
        self._client = client
        self._config = config
        self._auto_config = auto_config
        self._media_service = media_service  # you can't use ptz without media service
        self._media_profile: Any = None  # selected media profile for any PTZ operations
        self._onvif_ptz_service: Any = None  # ONVIF PTZ service instance
        self._ptz_config: Any = None  # to determine PTZ behaviour
        self._ptz_config_options: Any = None  # to determine PTZ options
        self._stop_patrol_event: asyncio.Event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize the PTZ service."""
        self._onvif_ptz_service = self._client.ptz()

        self._media_profile = self._media_service.get_selected_profile()

        self._ptz_config = await self.get_configurations()
        self._ptz_config_options = await self.get_configuration_options()

        if not self._auto_config and self._config:
            await self.apply_config()

    # ## Helper methods ## #

    def _adjust_pan_tilt(self, pan: float, tilt: float) -> tuple[float, float]:
        """Adjust pan/tilt values based on reverse settings."""
        if self._auto_config:
            return pan, tilt

        adjusted_pan = -pan if self._config.get(CONFIG_PTZ_REVERSE_PAN) else pan
        adjusted_tilt = -tilt if self._config.get(CONFIG_PTZ_REVERSE_TILT) else tilt
        return adjusted_pan, adjusted_tilt

    def _clamp_position(self, pan: float, tilt: float) -> tuple[float, float]:
        """Clamp pan/tilt values within configured limits."""
        if self._auto_config:
            return pan, tilt

        min_pan = self._config.get(CONFIG_PTZ_MIN_PAN)
        max_pan = self._config.get(CONFIG_PTZ_MAX_PAN)
        min_tilt = self._config.get(CONFIG_PTZ_MIN_TILT)
        max_tilt = self._config.get(CONFIG_PTZ_MAX_TILT)

        if min_pan is not None:
            pan = max(pan, min_pan)
        if max_pan is not None:
            pan = min(pan, max_pan)
        if min_tilt is not None:
            tilt = max(tilt, min_tilt)
        if max_tilt is not None:
            tilt = min(tilt, max_tilt)

        return pan, tilt

    def _clamp_zoom(self, zoom: float) -> float:
        """Clamp zoom value within configured limits."""
        if self._auto_config:
            return zoom

        min_zoom = self._config.get(CONFIG_PTZ_MIN_ZOOM)
        max_zoom = self._config.get(CONFIG_PTZ_MAX_ZOOM)

        if min_zoom is not None:
            zoom = max(zoom, min_zoom)
        if max_zoom is not None:
            zoom = min(zoom, max_zoom)

        return zoom

    async def _fire_and_forget(self, coro, timeout, *args, **kwargs):
        """Fire and forget a coroutine with a timeout."""
        coro_task = asyncio.create_task(coro(*args, **kwargs))
        if timeout > 0:
            asyncio.create_task(self._timeout_task(coro_task, timeout))

    async def _timeout_task(self, task, timeout):
        """Cancel a task after a set amount of time if given."""
        await asyncio.sleep(timeout)
        if not task.done():
            task.cancel()

    # ## The Real Operations ## #

    # ---- Movement Operations ---- #

    @operation()
    async def continuous_move(
        self,
        x_velocity: float,
        y_velocity: float,
        zoom_velocity: float = 0.0,
        seconds: float = 0.0,
    ) -> bool:
        """Move the camera continuously for a set amount of time."""
        adjusted_x, adjusted_y = self._adjust_pan_tilt(x_velocity, y_velocity)
        clamped_x, clamped_y = self._clamp_position(adjusted_x, adjusted_y)
        clamped_zoom = self._clamp_zoom(zoom_velocity)

        velocity = {"PanTilt": {"x": clamped_x, "y": clamped_y}}

        # Only add zoom param if supported
        if self._ptz_config_options.Spaces.ContinuousZoomVelocitySpace:
            velocity["Zoom"] = {"x": clamped_zoom}

        # Change seconds in ISO 8601
        timeout = f"PT{seconds}S"

        self._onvif_ptz_service.ContinuousMove(
            ProfileToken=self._media_profile.token,
            Velocity=velocity,
            Timeout=timeout if seconds > 0 else None,
        )
        return True

    @operation()
    async def relative_move(
        self,
        x_translation: float,
        y_translation: float,
        zoom_translation: float = 0.0,
        x_speed: float | None = None,
        y_speed: float | None = None,
        zoom_speed: float | None = None,
    ) -> bool:
        """Move the camera relative to its current position."""
        adjusted_x, adjusted_y = self._adjust_pan_tilt(x_translation, y_translation)
        clamped_x, clamped_y = self._clamp_position(adjusted_x, adjusted_y)
        clamped_zoom = self._clamp_zoom(zoom_translation)

        translation = {"PanTilt": {"x": clamped_x, "y": clamped_y}}
        default_speed = self._ptz_config[0].DefaultPTZSpeed
        speed: dict | None = None

        if x_speed is not None or y_speed is not None:
            speed = {
                "PanTilt": {
                    "x": x_speed if x_speed is not None else default_speed.PanTilt.x,
                    "y": y_speed if y_speed is not None else default_speed.PanTilt.y,
                }
            }

        # Only add zoom param if supported
        if self._ptz_config_options.Spaces.RelativeZoomTranslationSpace:
            translation["Zoom"] = {"x": clamped_zoom}

            if speed is None:
                speed = {}

            if zoom_speed is not None:
                speed["Zoom"] = {"x": zoom_speed}
            elif default_speed.Zoom is not None:
                speed["Zoom"] = {"x": default_speed.Zoom.x}

        self._onvif_ptz_service.RelativeMove(
            ProfileToken=self._media_profile.token,
            Translation=translation,
            Speed=speed,
        )
        return True

    @operation()
    async def absolute_move(
        self,
        x_position: float,
        y_position: float,
        zoom_position: float = 0.0,
        x_speed: float | None = None,
        y_speed: float | None = None,
        zoom_speed: float | None = None,
        is_adjusted: bool = True,  # Change to False for user-defined presets
    ) -> bool:
        """Move the camera to an absolute position."""
        if is_adjusted:
            adjusted_x, adjusted_y = self._adjust_pan_tilt(x_position, y_position)
        else:
            adjusted_x, adjusted_y = x_position, y_position

        clamped_x, clamped_y = self._clamp_position(adjusted_x, adjusted_y)
        clamped_zoom = self._clamp_zoom(zoom_position)

        position = {"PanTilt": {"x": clamped_x, "y": clamped_y}}
        default_speed = self._ptz_config[0].DefaultPTZSpeed
        speed: dict | None = None

        if x_speed is not None or y_speed is not None:
            speed = {
                "PanTilt": {
                    "x": x_speed if x_speed is not None else default_speed.PanTilt.x,
                    "y": y_speed if y_speed is not None else default_speed.PanTilt.y,
                }
            }

        # Only add zoom param if supported
        if self._ptz_config_options.Spaces.AbsoluteZoomPositionSpace:
            position["Zoom"] = {"x": clamped_zoom}

            if speed is None:
                speed = {}

            if zoom_speed is not None:
                speed["Zoom"] = {"x": zoom_speed}
            elif default_speed.Zoom is not None:
                speed["Zoom"] = {"x": default_speed.Zoom.x}

        self._onvif_ptz_service.AbsoluteMove(
            ProfileToken=self._media_profile.token,
            Position=position,
            Speed=speed,
        )
        return True

    @operation()
    async def stop(self) -> bool:
        """Stop any ongoing PTZ movement."""
        self._onvif_ptz_service.Stop(ProfileToken=self._media_profile.token)
        return True

    # ---- Position Operations ---- #

    @operation()
    async def goto_home_position(self) -> bool:
        """Move the camera to its home position."""
        self._onvif_ptz_service.GotoHomePosition(ProfileToken=self._media_profile.token)
        return True

    @operation()
    async def set_home_position(self) -> bool:
        """Set the current position as the home position."""
        self._onvif_ptz_service.SetHomePosition(ProfileToken=self._media_profile.token)
        return True

    @operation()
    async def get_status(self) -> Any:
        """Get the PTZ status of the camera."""
        return self._onvif_ptz_service.GetStatus(ProfileToken=self._media_profile.token)

    @operation()
    async def get_presets(self) -> Any:
        """Get the PTZ presets of the camera."""
        return self._onvif_ptz_service.GetPresets(
            ProfileToken=self._media_profile.token
        )

    @operation()
    async def goto_preset(self, preset_token: str) -> bool:
        """Move the camera to the specified preset."""
        self._onvif_ptz_service.GotoPreset(
            ProfileToken=self._media_profile.token,
            PresetToken=preset_token,
        )
        return True

    @operation()
    async def set_preset(self, preset_name: str) -> bool:
        """Set a preset at the current position with the given name."""
        return self._onvif_ptz_service.SetPreset(
            ProfileToken=self._media_profile.token,
            PresetName=preset_name,
        )

    @operation()
    async def remove_preset(self, preset_token: str) -> bool:
        """Remove the specified preset."""
        self._onvif_ptz_service.RemovePreset(
            ProfileToken=self._media_profile.token,
            PresetToken=preset_token,
        )
        return True

    # ---- Configuration Operations ---- #

    @operation()
    async def get_nodes(self) -> Any:
        """Get the PTZ nodes of the camera."""
        return self._onvif_ptz_service.GetNodes()

    @operation()
    async def get_configurations(self) -> Any:
        """Get the PTZ configurations of the camera."""
        return self._onvif_ptz_service.GetConfigurations()

    @operation()
    async def get_configuration_options(self) -> Any:
        """Get the PTZ configuration options of the camera."""
        return self._onvif_ptz_service.GetConfigurationOptions(
            ConfigurationToken=self._media_profile.PTZConfiguration.token
        )

    # ## Derived operations ## #

    def get_ptz_config(self) -> Any:
        """Get PTZ service from user-defined config."""
        if not self._auto_config:
            return self._config if self._config else None
        return None

    def get_configured_presets(self) -> list[str]:
        """Get the available presets for the camera from config."""
        if CONFIG_PTZ_PRESETS not in self._config:
            LOGGER.warning(f"No PTZ presets for camera {self._camera.identifier}")
            return []

        presets = self._config[CONFIG_PTZ_PRESETS]
        return list({preset[CONFIG_PTZ_PRESET_NAME] for preset in presets})

    async def get_position(self) -> tuple[float, float, float]:
        """Get the current position of the camera."""
        status = await self.get_status()
        if status and status.Position is not None:
            return (
                status.Position.PanTilt.x,
                status.Position.PanTilt.y,
                status.Position.Zoom.x if status.Position.Zoom else 0.0,
            )

        LOGGER.warning(f"Could not get PTZ status for camera {self._camera.identifier}")
        return 0.0, 0.0, 0.0

    async def pan_left(self, step_size: float = 0.1) -> bool:
        """Pan the camera to the left."""
        do_relative_move = await self.relative_move(
            x_translation=-step_size, y_translation=0.0
        )

        if not do_relative_move:
            return await self.continuous_move(
                x_velocity=-step_size, y_velocity=0.0, seconds=1
            )

        return do_relative_move

    async def pan_right(self, step_size: float = 0.1) -> bool:
        """Pan the camera to the right."""
        do_relative_move = await self.relative_move(
            x_translation=step_size, y_translation=0.0
        )

        if not do_relative_move:
            return await self.continuous_move(
                x_velocity=step_size, y_velocity=0.0, seconds=1
            )

        return do_relative_move

    async def tilt_up(self, step_size: float = 0.1) -> bool:
        """Tilt the camera up."""
        do_relative_move = await self.relative_move(
            x_translation=0.0, y_translation=step_size
        )

        if not do_relative_move:
            return await self.continuous_move(
                x_velocity=0.0, y_velocity=step_size, seconds=1
            )

        return do_relative_move

    async def tilt_down(self, step_size: float = 0.1) -> bool:
        """Tilt the camera down."""
        do_relative_move = await self.relative_move(
            x_translation=0.0, y_translation=-step_size
        )

        if not do_relative_move:
            return await self.continuous_move(
                x_velocity=0.0, y_velocity=-step_size, seconds=1
            )

        return do_relative_move

    async def zoom_in(self, step_size: float = 0.1) -> bool:
        """Zoom the camera in."""
        do_relative_move = await self.relative_move(
            x_translation=0.0, y_translation=0.0, zoom_translation=step_size
        )

        if not do_relative_move:
            return await self.continuous_move(
                x_velocity=0.0, y_velocity=0.0, zoom_velocity=step_size, seconds=1
            )

        return do_relative_move

    async def zoom_out(self, step_size: float = 0.1) -> bool:
        """Zoom the camera out."""
        do_relative_move = await self.relative_move(
            x_translation=0.0, y_translation=0.0, zoom_translation=-step_size
        )

        if not do_relative_move:
            return await self.continuous_move(
                x_velocity=0.0, y_velocity=0.0, zoom_velocity=-step_size, seconds=1
            )

        return do_relative_move

    # This operations moves the camera to a preset defined in the config and built-in
    # presets (based on name, and token as fallback) if not found in the config.
    async def move_to_preset(self, preset_name: str) -> bool:
        """Move the camera to a preset position."""
        if CONFIG_PTZ_PRESETS not in self._config:
            LOGGER.error(f"No PTZ presets for camera {self._camera.identifier}")
            return False

        if not any(
            preset[CONFIG_PTZ_PRESET_NAME] == preset_name
            for preset in self._config[CONFIG_PTZ_PRESETS]
        ):
            # Try to find preset from camera's own presets
            cam_presets = await self.get_presets()
            for cam_preset in cam_presets:
                if cam_preset.Name == preset_name:
                    return await self.goto_preset(cam_preset.token)
                if cam_preset.token == preset_name:
                    return await self.goto_preset(cam_preset.token)
            LOGGER.error(
                f"PTZ preset {preset_name} not found for camera "
                f"{self._camera.identifier}"
            )
            return False

        presets = self._config[CONFIG_PTZ_PRESETS]
        for preset in presets:
            if preset[CONFIG_PTZ_PRESET_NAME] == preset_name:
                return await self.absolute_move(
                    x_position=preset[CONFIG_PTZ_PRESET_PAN],
                    y_position=preset[CONFIG_PTZ_PRESET_TILT],
                    zoom_position=preset[CONFIG_PTZ_PRESET_ZOOM]
                    if CONFIG_PTZ_PRESET_ZOOM in preset
                    else 0.0,
                    is_adjusted=False,
                )
        return False

    async def absolute_move_wait_complete(
        self, pan: float, tilt: float, timeout: float = 1.0, zoom: float = 0.0
    ) -> bool:
        """Move the camera to an absolute position and wait for completion."""
        if not await self.absolute_move(
            x_position=pan, y_position=tilt, zoom_position=zoom
        ):
            return False

        tolerance = 0.005
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            status = await self.get_status()
            if not status or not status.Position or not status.Position.PanTilt:
                await asyncio.sleep(0.1)
                continue

            if (
                abs(status.Position.PanTilt.x - pan) <= tolerance
                and abs(status.Position.PanTilt.y - tilt) <= tolerance
            ):
                LOGGER.debug(
                    "Position at end of abs move and wait (requested: %s): %s",
                    (pan, tilt),
                    status,
                )
                return True

            await asyncio.sleep(0.1)

        LOGGER.debug(
            "Timeout waiting for PTZ move to (%s, %s)",
            pan,
            tilt,
        )
        return False

    async def patrol(
        self,
        duration: int = 60,
        sleep_after_swing: int = 6,
        step_size: float = 0.3,
        step_sleep_time: float = 0.1,
    ) -> None:
        """Perform a patrol of the camera.

        Args:
            duration: Duration of the patrol in seconds
            sleep_after_swing: Time to sleep after each swing
            step_size: Size of each movement step
            step_sleep_time: Time to sleep between movement steps
        """
        if self._stop_patrol_event is not None:
            self._stop_patrol_event.clear()

        await self._fire_and_forget(
            self._do_patrol,
            duration,
            sleep_after_swing=sleep_after_swing,
            step_size=step_size,
            step_sleep_time=step_sleep_time,
        )

    async def _do_patrol(
        self,
        step_size: float = 0.3,
        step_sleep_time: float = 0.1,
        sleep_after_swing=6,
    ):
        """Perform a patrol of the camera."""
        try:
            # Get and store starting position
            status = await self.get_status()
            if status is None or status.Position is None:
                LOGGER.warning("Cannot determine starting position")
                initial_pan = 0.0
                initial_tilt = 0.0
            else:
                initial_pan = status.Position.PanTilt.x
                initial_tilt = status.Position.PanTilt.y
                LOGGER.debug(
                    f"Camera position at start: x: {initial_pan}, y: {initial_tilt}"
                )

            # Get the camera's FOV limits, if any
            min_pan = self._config.get(CONFIG_PTZ_MIN_PAN)
            max_pan = self._config.get(CONFIG_PTZ_MAX_PAN)
            min_tilt = self._config.get(CONFIG_PTZ_MIN_TILT)
            max_tilt = self._config.get(CONFIG_PTZ_MAX_TILT)

            # Decide which direction to start swinging based on distance to limits
            distance_to_min = initial_pan - min_pan if min_pan else 0
            distance_to_max = max_pan - initial_pan if max_pan else 0
            left = distance_to_min > distance_to_max

            # Swing back and forth until stopped
            while not self._stop_patrol_event.is_set():
                await self.full_swing(
                    is_left=left,
                    step_size=step_size,
                    step_sleep_time=step_sleep_time,
                    min_pan=min_pan,
                    max_pan=max_pan,
                    min_tilt=min_tilt,
                    max_tilt=max_tilt,
                )
                if self._stop_patrol_event.is_set():
                    break
                await asyncio.sleep(sleep_after_swing)
                left = not left

        finally:
            # Move back to the initial position
            await self.absolute_move(x_position=initial_pan, y_position=initial_tilt)

    async def full_swing(
        self,
        is_left: bool = True,
        step_size: float = 0.3,
        step_sleep_time: float = 0.1,
        min_pan: float | None = None,
        max_pan: float | None = None,
        min_tilt: float | None = None,
        max_tilt: float | None = None,
    ):
        """Perform a full swing in the pan direction.

        Args:
            is_left: True if the swing is to the left, False if to the right
            step_size: The size of each move step
            step_sleep_time: Time to sleep between each move step
            min_pan: Minimum pan value to stop at
            max_pan: Maximum pan value to stop at
            min_tilt: Minimum tilt value (for validation)
            max_tilt: Maximum tilt value (for validation)
        """
        if not self._onvif_ptz_service:
            LOGGER.error(
                f"PTZ service not initialized for camera {self._camera.identifier}"
            )
            return

        status = await self.get_status()
        cur_pan = status.Position.PanTilt.x
        cur_tilt = status.Position.PanTilt.y
        LOGGER.debug(
            f"Fullswing start: pan: {cur_pan}, tilt: {cur_tilt}, "
            f"limits: pan[{min_pan}, {max_pan}], tilt[{min_tilt}, {max_tilt}]"
        )

        move_step = -abs(step_size) if is_left else abs(step_size)

        # Do not move beyond the camera's FOV bounds
        if is_left:
            if min_pan is not None and cur_pan + move_step <= min_pan:
                return
        else:
            if max_pan is not None and cur_pan + move_step >= max_pan:
                return

        # Move while not stopped or stopped by the camera's FOV or hardware bounds
        while (
            await self.relative_move(x_translation=move_step, y_translation=0.0)
            and not self._stop_patrol_event.is_set()
        ):
            await asyncio.sleep(step_sleep_time)
            status = await self.get_status()
            cur_pan = status.Position.PanTilt.x
            cur_tilt = status.Position.PanTilt.y
            LOGGER.debug(f"Fullswing moved to: pan: {cur_pan}, tilt: {cur_tilt}")
            if min_pan is not None and cur_pan <= min_pan:
                break
            if max_pan is not None and cur_pan >= max_pan:
                break

        LOGGER.debug(
            f"Fullswing end: pan: {cur_pan}, tilt: {cur_tilt}, "
            f"limits: pan[{min_pan}, {max_pan}], tilt[{min_tilt}, {max_tilt}]"
        )

    async def lissajous_curve_patrol(
        self,
        pan_amp: float = 1.0,
        pan_freq: float = 0.1,
        tilt_amp: float = 1.0,
        tilt_freq: float = 0.1,
        phase_shift: float = np.pi / 2,
        step_sleep_time: float = 0.1,
    ):
        """Perform a Lissajous curve patrol.

        Args:
            pan_amp: Pan amplitude
            pan_freq: Pan frequency
            tilt_amp: Tilt amplitude
            tilt_freq: Tilt frequency
            phase_shift: Phase shift between pan and tilt
            step_sleep_time: Time to sleep between movements
        """

        if self._stop_patrol_event is not None:
            self._stop_patrol_event.clear()

        # Start a new patrol
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
        """Perform a Lissajous curve patrol."""
        try:
            # Get and store starting position
            status = await self.get_status()
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

                if self._stop_patrol_event.is_set():
                    break

                await self.absolute_move_wait_complete(pan=x, tilt=y)
                await asyncio.sleep(step_sleep_time)

        finally:
            # Move back to the initial position
            await self.absolute_move(x_position=initial_pan, y_position=initial_tilt)

    def stop_patrol(self) -> bool:
        """Stop the patrol event."""
        try:
            if self._stop_patrol_event:
                self._stop_patrol_event.set()
                # await self.stop()# It is required to stop all PTZ movements operations
                return True
            return False
        except RuntimeError as error:
            LOGGER.error(f"Error stopping patrol: {error}")
            return False

    # ## Apply Configuration at Startup ## #

    async def apply_config(self) -> bool:
        """Apply all configured device settings from config."""
        try:
            home_position = self._config.get(CONFIG_PTZ_HOME_POSITION, False)
            presets = self._config.get(CONFIG_PTZ_PRESETS, [])
            has_on_startup = any(
                preset.get(CONFIG_PTZ_PRESET_ON_STARTUP, False) for preset in presets
            )

            # Move to home position if configured
            if home_position and not has_on_startup:
                await self.goto_home_position()
                LOGGER.debug(
                    f"PTZ Go Home Position executed for {self._camera.identifier}"
                )

            # Move to startup preset if configured
            if presets:
                for preset in presets:
                    if preset.get(CONFIG_PTZ_PRESET_ON_STARTUP, False):
                        await self.move_to_preset(preset[CONFIG_PTZ_PRESET_NAME])
                        LOGGER.debug(
                            f"PTZ Move to Preset "
                            f"{preset[CONFIG_PTZ_PRESET_NAME]} executed for "
                            f"{self._camera.identifier}"
                        )

            LOGGER.info(
                f"PTZ service configuration for {self._camera.identifier} "
                f"has been applied."
            )
        except (ValueError, AttributeError) as error:
            LOGGER.error(
                f"Error applying PTZ service configuration for "
                f"{self._camera.identifier}: {error}"
            )
            return False
        return True
