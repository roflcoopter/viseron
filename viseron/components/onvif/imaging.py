"""Imaging service management for ONVIF component."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from onvif import ONVIFClient

from .const import (
    CONFIG_IMAGING_BACKLIGHT_COMPENSATION,
    CONFIG_IMAGING_BRIGHTNESS,
    CONFIG_IMAGING_COLOR_SATURATION,
    CONFIG_IMAGING_CONTRAST,
    CONFIG_IMAGING_DEFOGGING,
    CONFIG_IMAGING_EXPOSURE,
    CONFIG_IMAGING_FOCUS,
    CONFIG_IMAGING_FORCE_PERSISTENCE,
    CONFIG_IMAGING_IMAGE_STABILIZATION,
    CONFIG_IMAGING_IRCUT_FILTER,
    CONFIG_IMAGING_IRCUT_FILTER_AUTO_ADJUSTMENT,
    CONFIG_IMAGING_NOISE_REDUCTION,
    CONFIG_IMAGING_SHARPNESS,
    CONFIG_IMAGING_TONE_COMPENSATION,
    CONFIG_IMAGING_WHITE_BALANCE,
    CONFIG_IMAGING_WIDE_DYNAMIC_RANGE,
    DEFAULT_IMAGING_FORCE_PERSISTENCE,
)
from .utils import operation

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


class Imaging:
    """Class for managing Imaging operations for an ONVIF camera."""

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
        self._media_service = (
            media_service  # you can't use imaging without media service
        )
        self._media_profile: Any = None  # selected media profile
        self._onvif_imaging_service: Any = None  # ONVIF Imaging service instance
        self._video_source_token: str | None = None

    async def initialize(self) -> None:
        """Initialize the Imaging service."""

        self._onvif_imaging_service = self._client.imaging()

        self._media_profile = self._media_service.get_selected_profile()
        self._video_source_token = (
            self._media_profile.VideoSourceConfiguration.SourceToken
        )

        if not self._auto_config and self._config:
            await self.apply_config()

    # ## Helper methods ## #

    def _nested_dict(self):
        return defaultdict(self._nested_dict)

    def _has_data(self, d):
        return any(
            isinstance(v, dict) and self._has_data(v) or v is not None
            for v in d.values()
        )

    def _to_dict(self, obj):
        if isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        return obj

    def _snake_to_camel(self, s: str) -> str:
        if "_" in s:
            return "".join(word.capitalize() for word in s.split("_"))
        return s[0].upper() + s[1:] if s else s

    def _convert_keys_to_camel(self, obj):
        if isinstance(obj, dict):
            return {
                self._snake_to_camel(k): self._convert_keys_to_camel(v)
                for k, v in obj.items()
            }

        if isinstance(obj, list):
            return [self._convert_keys_to_camel(item) for item in obj]

        return obj

    # ## The Real Operations ## #

    # ---- Settings Operations ---- #

    @operation()
    async def get_options(self) -> Any:
        """Get available imaging options."""
        return self._onvif_imaging_service.GetOptions(
            VideoSourceToken=self._video_source_token
        )

    @operation()
    async def get_imaging_settings(self) -> Any:
        """Get current imaging settings."""
        return self._onvif_imaging_service.GetImagingSettings(
            VideoSourceToken=self._video_source_token,
        )

    @operation()
    async def set_imaging_settings(
        self, settings: dict[str, Any], force_persistence: bool = True
    ) -> bool:
        """Set imaging settings."""
        self._onvif_imaging_service.SetImagingSettings(
            VideoSourceToken=self._video_source_token,
            ImagingSettings=self._convert_keys_to_camel(self._to_dict(settings)),
            ForcePersistence=force_persistence,
        )
        return True

    # ---- Focus Operations ---- #

    @operation()
    async def get_move_options(self) -> Any:
        """Get available move options."""
        return self._onvif_imaging_service.GetMoveOptions(
            VideoSourceToken=self._video_source_token
        )

    @operation()
    async def get_status(self) -> bool:
        """Get focus movement status."""
        self._onvif_imaging_service.GetStatus(
            VideoSourceToken=self._video_source_token,
        )
        return True

    @operation()
    async def move_focus(self, move_config: dict[str, Any]) -> bool:
        """Move focus continuously or relatively."""
        self._onvif_imaging_service.Move(
            VideoSourceToken=self._video_source_token,
            Focus=move_config,
        )
        return True

    @operation()
    async def stop_focus(self) -> bool:
        """Stop focus movement."""
        self._onvif_imaging_service.Stop(
            VideoSourceToken=self._video_source_token,
        )
        return True

    # ## Derived operations ## #

    async def set_brightness(
        self, force_persistence: bool, brightness: float | None = None
    ) -> bool:
        """Set brightness level."""
        if not self._auto_config and brightness is None:
            brightness = self._config.get(CONFIG_IMAGING_BRIGHTNESS)

        if brightness is not None:
            return await self.set_imaging_settings(
                {"Brightness": brightness}, force_persistence
            )

        return False

    async def set_color_saturation(
        self, force_persistence: bool, saturation: float | None = None
    ) -> bool:
        """Set color saturation level."""
        if not self._auto_config and saturation is None:
            saturation = self._config.get(CONFIG_IMAGING_COLOR_SATURATION)

        if saturation is not None:
            return await self.set_imaging_settings(
                {"ColorSaturation": saturation}, force_persistence
            )

        return False

    async def set_contrast(
        self, force_persistence: bool, contrast: float | None = None
    ) -> bool:
        """Set contrast level."""
        if not self._auto_config and contrast is None:
            contrast = self._config.get(CONFIG_IMAGING_CONTRAST)

        if contrast is not None:
            return await self.set_imaging_settings(
                {"Contrast": contrast}, force_persistence
            )

        return False

    async def set_sharpness(
        self, force_persistence: bool, sharpness: float | None = None
    ) -> bool:
        """Set sharpness level."""
        if not self._auto_config and sharpness is None:
            sharpness = self._config.get(CONFIG_IMAGING_SHARPNESS)

        if sharpness is not None:
            return await self.set_imaging_settings(
                {"Sharpness": sharpness}, force_persistence
            )

        return False

    async def set_ircut_filter(
        self, force_persistence: bool, ircut_filter: str | None = None
    ) -> bool:
        """Set IR cut filter mode."""
        if not self._auto_config and ircut_filter is None:
            ircut_filter = self._config.get(CONFIG_IMAGING_IRCUT_FILTER)

        if ircut_filter is not None:
            return await self.set_imaging_settings(
                {"IrCutFilter": ircut_filter}, force_persistence
            )

        return False

    async def set_backlight_compensation(
        self, force_persistence: bool, blc_mode: str | None = None
    ) -> bool:
        """Set backlight compensation settings."""
        if not self._auto_config and blc_mode is None:
            blc_mode = self._config.get(CONFIG_IMAGING_BACKLIGHT_COMPENSATION)

        if blc_mode is not None:
            return await self.set_imaging_settings(
                {"BacklightCompensation": {"Mode": blc_mode}}, force_persistence
            )

        return False

    async def set_exposure(
        self, force_persistence: bool, exposure_config: dict[str, Any] | None = None
    ) -> bool:
        """Set exposure settings."""
        if not self._auto_config and exposure_config is None:
            exposure_config = self._config.get(CONFIG_IMAGING_EXPOSURE)

        if exposure_config is not None:
            return await self.set_imaging_settings(
                {"Exposure": exposure_config}, force_persistence
            )

        return False

    async def set_focus(
        self, force_persistence: bool, focus_config: dict[str, Any] | None = None
    ) -> bool:
        """Set focus settings."""
        if not self._auto_config and focus_config is None:
            focus_config = self._config.get(CONFIG_IMAGING_FOCUS)

        if focus_config is not None:
            return await self.set_imaging_settings(
                {"Focus": focus_config}, force_persistence
            )

        return False

    async def set_wide_dynamic_range(
        self, force_persistence: bool, wdr_config: dict[str, Any] | None = None
    ) -> bool:
        """Set wide dynamic range settings."""
        if not self._auto_config and wdr_config is None:
            wdr_config = self._config.get(CONFIG_IMAGING_WIDE_DYNAMIC_RANGE)

        if wdr_config is not None:
            return await self.set_imaging_settings(
                {"WideDynamicRange": wdr_config}, force_persistence
            )

        return False

    async def set_white_balance(
        self, force_persistence: bool, wb_config: dict[str, Any] | None = None
    ) -> bool:
        """Set white balance settings."""
        if not self._auto_config and wb_config is None:
            wb_config = self._config.get(CONFIG_IMAGING_WHITE_BALANCE)

        if wb_config is not None:
            return await self.set_imaging_settings(
                {"WhiteBalance": wb_config}, force_persistence
            )

        return False

    async def set_image_stabilization(
        self, force_persistence: bool, is_config: dict[str, Any] | None = None
    ) -> bool:
        """Set image stabilization settings."""
        if not self._auto_config and is_config is None:
            is_config = self._config.get(CONFIG_IMAGING_IMAGE_STABILIZATION)

        if is_config is not None:
            return await self.set_imaging_settings(
                {"Extension": {"ImageStabilization": is_config}}, force_persistence
            )

        return False

    async def set_ircut_filter_auto_adjustment(
        self, force_persistence: bool, ifaa_config: dict[str, Any] | None = None
    ) -> bool:
        """Set ircut filter auto adjustment settings."""
        if not self._auto_config and ifaa_config is None:
            ifaa_config = self._config.get(CONFIG_IMAGING_IRCUT_FILTER_AUTO_ADJUSTMENT)

        if ifaa_config is not None:
            return await self.set_imaging_settings(
                {
                    "Extension": {
                        "Extension": {"IrCutFilterAutoAdjustment": ifaa_config}
                    }
                },
                force_persistence,
            )

        return False

    async def set_tone_compensation(
        self, force_persistence: bool, tc_config: dict[str, Any] | None = None
    ) -> bool:
        """Set tone compensation settings."""
        if not self._auto_config and tc_config is None:
            tc_config = self._config.get(CONFIG_IMAGING_TONE_COMPENSATION)

        if tc_config is not None:
            return await self.set_imaging_settings(
                {
                    "Extension": {
                        "Extension": {"Extension": {"ToneCompensation": tc_config}}
                    }
                },
                force_persistence,
            )

        return False

    async def set_defogging(
        self, force_persistence: bool, d_config: dict[str, Any] | None = None
    ) -> bool:
        """Set defogging settings."""
        if not self._auto_config and d_config is None:
            d_config = self._config.get(CONFIG_IMAGING_DEFOGGING)

        if d_config is not None:
            return await self.set_imaging_settings(
                {"Extension": {"Extension": {"Extension": {"Defogging": d_config}}}},
                force_persistence,
            )

        return False

    async def set_noise_reduction(
        self, force_persistence: bool, nr_config: dict[str, Any] | None = None
    ) -> bool:
        """Set noise reduction settings."""
        if not self._auto_config and nr_config is None:
            nr_config = self._config.get(CONFIG_IMAGING_NOISE_REDUCTION)

        if nr_config is not None:
            return await self.set_imaging_settings(
                {
                    "Extension": {
                        "Extension": {"Extension": {"NoiseReduction": nr_config}}
                    }
                },
                force_persistence,
            )

        return False

    # ## Apply Configuration at Startup ## #

    async def apply_config(self) -> bool:
        """Apply all configured imaging settings from config."""
        try:
            force_persistence = self._config.get(
                CONFIG_IMAGING_FORCE_PERSISTENCE, DEFAULT_IMAGING_FORCE_PERSISTENCE
            )

            settings = {}

            # ---- Flat settings ----

            if CONFIG_IMAGING_BRIGHTNESS in self._config:
                settings["Brightness"] = self._config[CONFIG_IMAGING_BRIGHTNESS]

            if CONFIG_IMAGING_COLOR_SATURATION in self._config:
                settings["ColorSaturation"] = self._config[
                    CONFIG_IMAGING_COLOR_SATURATION
                ]

            if CONFIG_IMAGING_CONTRAST in self._config:
                settings["Contrast"] = self._config[CONFIG_IMAGING_CONTRAST]

            if CONFIG_IMAGING_SHARPNESS in self._config:
                settings["Sharpness"] = self._config[CONFIG_IMAGING_SHARPNESS]

            if CONFIG_IMAGING_IRCUT_FILTER in self._config:
                settings["IrCutFilter"] = self._config[
                    CONFIG_IMAGING_IRCUT_FILTER
                ].upper()

            if CONFIG_IMAGING_BACKLIGHT_COMPENSATION in self._config:
                settings["BacklightCompensation"] = {
                    "Mode": self._config[CONFIG_IMAGING_BACKLIGHT_COMPENSATION].upper()
                }

            if CONFIG_IMAGING_EXPOSURE in self._config:
                settings["Exposure"] = self._config[CONFIG_IMAGING_EXPOSURE]

            if CONFIG_IMAGING_FOCUS in self._config:
                settings["Focus"] = self._config[CONFIG_IMAGING_FOCUS]

            if CONFIG_IMAGING_WIDE_DYNAMIC_RANGE in self._config:
                settings["WideDynamicRange"] = self._config[
                    CONFIG_IMAGING_WIDE_DYNAMIC_RANGE
                ]

            if CONFIG_IMAGING_WHITE_BALANCE in self._config:
                settings["WhiteBalance"] = self._config[CONFIG_IMAGING_WHITE_BALANCE]

            # ---- Extensions (nested safely) ----

            ext = self._nested_dict()

            if CONFIG_IMAGING_IMAGE_STABILIZATION in self._config:
                ext["ImageStabilization"] = self._config[
                    CONFIG_IMAGING_IMAGE_STABILIZATION
                ]

            if CONFIG_IMAGING_IRCUT_FILTER_AUTO_ADJUSTMENT in self._config:
                ext["Extension"]["IrCutFilterAutoAdjustment"] = self._config[
                    CONFIG_IMAGING_IRCUT_FILTER_AUTO_ADJUSTMENT
                ]

            if CONFIG_IMAGING_TONE_COMPENSATION in self._config:
                ext["Extension"]["Extension"]["ToneCompensation"] = self._config[
                    CONFIG_IMAGING_TONE_COMPENSATION
                ]

            if CONFIG_IMAGING_DEFOGGING in self._config:
                ext["Extension"]["Extension"]["Defogging"] = self._config[
                    CONFIG_IMAGING_DEFOGGING
                ]

            if CONFIG_IMAGING_NOISE_REDUCTION in self._config:
                ext["Extension"]["Extension"]["NoiseReduction"] = self._config[
                    CONFIG_IMAGING_NOISE_REDUCTION
                ]

            if self._has_data(ext):
                settings["Extension"] = ext

            set_imaging_settings = await self.set_imaging_settings(
                settings, force_persistence
            )

            if set_imaging_settings:
                LOGGER.info(
                    f"Imaging service configuration for {self._camera.identifier} "
                    f"has been applied."
                )
                return True

            LOGGER.error(
                f"Error applying Imaging service configuration for "
                f"{self._camera.identifier}!"
            )
            return False
        except (ValueError, AttributeError) as error:
            LOGGER.error(
                f"Error applying Imaging service configuration for "
                f"{self._camera.identifier}: {error}"
            )
            return False
