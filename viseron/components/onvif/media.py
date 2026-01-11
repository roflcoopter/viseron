"""Media service management for ONVIF component."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from onvif import ONVIFClient

from .const import (
    CONFIG_AUDIO_BITRATE,
    CONFIG_AUDIO_ENCODER,
    CONFIG_AUDIO_ENCODING,
    CONFIG_AUDIO_FORCE_PERSISTENCE,
    CONFIG_AUDIO_SAMPLE_RATE,
    CONFIG_VIDEO_BITRATE,
    CONFIG_VIDEO_ENCODER,
    CONFIG_VIDEO_ENCODING,
    CONFIG_VIDEO_ENCODING_INTERVAL,
    CONFIG_VIDEO_FORCE_PERSISTENCE,
    CONFIG_VIDEO_FRAME_RATE,
    CONFIG_VIDEO_GOV_LENGTH,
    CONFIG_VIDEO_H264,
    CONFIG_VIDEO_MPEG4,
    CONFIG_VIDEO_QUALITY,
    CONFIG_VIDEO_RESOLUTION,
    CONFIG_VIDEO_RESOLUTION_HEIGHT,
    CONFIG_VIDEO_RESOLUTION_WIDTH,
    DEFAULT_AUDIO_FORCE_PERSISTENCE,
    DEFAULT_VIDEO_FORCE_PERSISTENCE,
)
from .utils import find_matching_profile_token, operation

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


class Media:
    """Class for managing Media operations for an ONVIF camera."""

    def __init__(
        self,
        camera: AbstractCamera,
        client: ONVIFClient,
        config: dict[str, Any],
        auto_config: bool = True,
    ) -> None:
        self._camera = camera
        self._client = client
        self._config = config
        self._auto_config = auto_config
        self._media_service: Any = None
        self._selected_profile: Any = None
        self._profiles: list[Any] = []

    async def initialize(self) -> None:
        """Initialize the Media service."""
        self._media_service = self._client.media()

        # Load media profiles
        self._profiles = await self.get_profiles()
        if self._profiles:
            # Try to find matching profile based on camera's RTSP URL
            self._selected_profile = await find_matching_profile_token(
                self._camera, self, self._profiles
            )

            if self._selected_profile:
                LOGGER.debug(
                    f"Using matching profile {self._selected_profile.token} for "
                    f"Media service on camera {self._camera.identifier}"
                )
            else:
                # Fallback to first profile
                self._selected_profile = self._profiles[0]
                LOGGER.warning(
                    f"No matching profile found, using first profile for "
                    f"Media service on camera {self._camera.identifier}"
                )
        else:
            LOGGER.warning(
                f"No media profiles found for {self._camera.identifier}, "
                "Media operations may not work correctly"
            )

        if not self._auto_config and self._config:
            await self.apply_config()

    # ## The Real Operations ## #

    # ---- Profiles Operations ---- #

    @operation()
    async def get_profiles(self) -> Any:
        """Get media profiles."""
        return self._media_service.GetProfiles()

    @operation()
    async def get_profile(self, profile_token: str) -> Any:
        """Get a specific media profile."""
        return self._media_service.GetProfile(ProfileToken=profile_token)

    @operation()
    async def create_profile(self, name: str, token: str | None = None) -> Any:
        """Create a new media profile."""
        return self._media_service.CreateProfile(Name=name, Token=token)

    @operation()
    async def delete_profile(self, profile_token: str) -> bool:
        """Delete a media profile."""
        self._media_service.DeleteProfile(ProfileToken=profile_token)
        return True

    # ---- URI Operations ---- #

    @operation()
    async def get_stream_uri(
        self,
        profile_token: str | None = None,
        stream_type: str = "RTP-Unicast",
        protocol: str = "RTSP",
    ) -> Any:
        """Get stream URI for a profile."""
        stream_setup = {"Stream": stream_type, "Transport": {"Protocol": protocol}}
        return self._media_service.GetStreamUri(
            StreamSetup=stream_setup,
            ProfileToken=profile_token or self._selected_profile.token,
        )

    @operation()
    async def get_snapshot_uri(self, profile_token: str | None = None) -> Any:
        """Get snapshot URI for a profile."""
        return self._media_service.GetSnapshotUri(
            ProfileToken=profile_token or self._selected_profile.token
        )

    # ---- Video Operations ---- #

    @operation()
    async def get_video_encoder_configuration(
        self, config_token: str | None = None
    ) -> Any:
        """Get video encoder configuration."""
        return self._media_service.GetVideoEncoderConfiguration(
            ConfigurationToken=config_token
            or self._selected_profile.VideoEncoderConfiguration.token
        )

    @operation()
    async def get_video_encoder_configuration_options(
        self, config_token: str | None = None
    ) -> Any:
        """Get video encoder configuration options."""
        return self._media_service.GetVideoEncoderConfigurationOptions(
            ConfigurationToken=config_token
            or self._selected_profile.VideoEncoderConfiguration.token
        )

    @operation()
    async def set_video_encoder_configuration(
        self, configuration: dict[str, Any], force_persistence: bool = True
    ) -> bool:
        """Set video encoder configuration for a profile."""

        if not configuration.get("token"):
            configuration[
                "token"
            ] = self._selected_profile.VideoEncoderConfiguration.token

        if not configuration.get("Name"):
            configuration[
                "Name"
            ] = self._selected_profile.VideoEncoderConfiguration.Name

        self._media_service.SetVideoEncoderConfiguration(
            Configuration=configuration, ForcePersistence=force_persistence
        )
        return True

    # ---- Audio Operations ---- #

    @operation()
    async def get_audio_encoder_configuration(
        self, config_token: str | None = None
    ) -> Any:
        """Get audio encoder configurations."""
        return self._media_service.GetAudioEncoderConfiguration(
            ConfigurationToken=config_token
            or self._selected_profile.AudioEncoderConfiguration.token
        )

    @operation()
    async def get_audio_encoder_configuration_options(
        self, config_token: str | None = None
    ) -> Any:
        """Get audio encoder configuration options."""
        return self._media_service.GetAudioEncoderConfigurationOptions(
            ConfigurationToken=config_token
            or self._selected_profile.AudioEncoderConfiguration.token
        )

    @operation()
    async def set_audio_encoder_configuration(
        self, configuration: dict[str, Any], force_persistence: bool = True
    ) -> bool:
        """Set audio encoder configuration for a profile."""

        if not configuration.get("token"):
            configuration[
                "token"
            ] = self._selected_profile.AudioEncoderConfiguration.token

        if not configuration.get("Name"):
            configuration[
                "Name"
            ] = self._selected_profile.AudioEncoderConfiguration.Name

        self._media_service.SetAudioEncoderConfiguration(
            Configuration=configuration, ForcePersistence=force_persistence
        )
        return True

    # ---- OSD Operations ---- #

    @operation()
    async def get_osd(self, token: str) -> Any:
        """Get on-screen display configuration."""
        return self._media_service.GetOSD(OSDToken=token)

    @operation()
    async def get_osds(self, config_token: str | None = None) -> Any:
        """Get all on-screen display configurations."""
        return self._media_service.GetOSDs(
            ConfigurationToken=config_token
            or self._selected_profile.VideoSourceConfiguration.token
        )

    @operation()
    async def get_osd_options(self, config_token: str | None = None) -> Any:
        """Get on-screen display configuration options."""
        return self._media_service.GetOSDOptions(
            ConfigurationToken=config_token
            or self._selected_profile.VideoSourceConfiguration.token
        )

    @operation()
    async def create_osd(self, osd_config: dict[str, Any]) -> bool:
        """Create new on-screen display configuration."""

        if not osd_config.get("VideoSourceConfigurationToken"):
            osd_config[
                "VideoSourceConfigurationToken"
            ] = self._selected_profile.VideoSourceConfiguration.token

        self._media_service.CreateOSD(OSD=osd_config)
        return True

    @operation()
    async def delete_osd(self, token: str) -> bool:
        """Delete on-screen display configuration."""
        self._media_service.DeleteOSD(OSDToken=token)
        return True

    @operation()
    async def set_osd(self, osd_config: dict[str, Any]) -> bool:
        """Set existing on-screen display configuration."""

        if not osd_config.get("VideoSourceConfigurationToken"):
            osd_config[
                "VideoSourceConfigurationToken"
            ] = self._selected_profile.VideoSourceConfiguration.token

        self._media_service.SetOSD(OSD=osd_config)
        return True

    # ## Profile Accessors ## #

    def get_selected_profile(self):
        """Get selected media profile without making ONVIF call."""
        return self._selected_profile

    def get_primary_profile(self):
        """Get the primary (first) media profile."""
        return self._profiles[0] if self._profiles else None

    def get_profile_by_token(self, token: str):
        """Get a profile by its token."""
        for profile in self._profiles:
            if profile.token == token:
                return profile
        return None

    # ## Apply Configuration at Startup ## #

    async def apply_config(self) -> bool:
        """Apply all configured device settings from config."""
        try:
            set_video_encoder_config = False
            set_audio_encoder_config = False

            # ---- Video Encoder config ----

            if CONFIG_VIDEO_ENCODER in self._config:
                video_force_persistence = self._config[CONFIG_VIDEO_ENCODER].get(
                    CONFIG_VIDEO_FORCE_PERSISTENCE, DEFAULT_VIDEO_FORCE_PERSISTENCE
                )

                video_config = {
                    "token": self._selected_profile.VideoEncoderConfiguration.token,
                    "Name": self._selected_profile.VideoEncoderConfiguration.Name,
                    "Encoding": self._config[CONFIG_VIDEO_ENCODER][
                        CONFIG_VIDEO_ENCODING
                    ],
                    "Resolution": {
                        "Width": self._config[CONFIG_VIDEO_ENCODER][
                            CONFIG_VIDEO_RESOLUTION
                        ][CONFIG_VIDEO_RESOLUTION_WIDTH],
                        "Height": self._config[CONFIG_VIDEO_ENCODER][
                            CONFIG_VIDEO_RESOLUTION
                        ][CONFIG_VIDEO_RESOLUTION_HEIGHT],
                    },
                }

                if CONFIG_VIDEO_QUALITY in self._config[CONFIG_VIDEO_ENCODER]:
                    video_config["Quality"] = self._config[CONFIG_VIDEO_ENCODER][
                        CONFIG_VIDEO_QUALITY
                    ]

                rate_control = {}

                if CONFIG_VIDEO_FRAME_RATE in self._config[CONFIG_VIDEO_ENCODER]:
                    rate_control["FrameRateLimit"] = self._config[CONFIG_VIDEO_ENCODER][
                        CONFIG_VIDEO_FRAME_RATE
                    ]

                if CONFIG_VIDEO_ENCODING_INTERVAL in self._config[CONFIG_VIDEO_ENCODER]:
                    rate_control["EncodingInterval"] = self._config[
                        CONFIG_VIDEO_ENCODER
                    ][CONFIG_VIDEO_ENCODING_INTERVAL]

                if CONFIG_VIDEO_BITRATE in self._config[CONFIG_VIDEO_ENCODER]:
                    rate_control["BitrateLimit"] = self._config[CONFIG_VIDEO_ENCODER][
                        CONFIG_VIDEO_BITRATE
                    ]

                if rate_control:
                    video_config["RateControl"] = rate_control

                if self._config[CONFIG_VIDEO_ENCODER][CONFIG_VIDEO_ENCODING] == "H264":
                    h264_config = video_config.setdefault("H264", {})
                    if CONFIG_VIDEO_H264 in self._config[CONFIG_VIDEO_ENCODER]:
                        h264_config["H264Profile"] = self._config[CONFIG_VIDEO_ENCODER][
                            CONFIG_VIDEO_H264
                        ]
                    if CONFIG_VIDEO_GOV_LENGTH in self._config[CONFIG_VIDEO_ENCODER]:
                        h264_config["GovLength"] = self._config[CONFIG_VIDEO_ENCODER][
                            CONFIG_VIDEO_GOV_LENGTH
                        ]

                if self._config[CONFIG_VIDEO_ENCODER][CONFIG_VIDEO_ENCODING] == "MPEG4":
                    mpeg4_config = video_config.setdefault("MPEG4", {})
                    if CONFIG_VIDEO_MPEG4 in self._config[CONFIG_VIDEO_ENCODER]:
                        mpeg4_config["Mpeg4Profile"] = self._config[
                            CONFIG_VIDEO_ENCODER
                        ][CONFIG_VIDEO_MPEG4]
                    if CONFIG_VIDEO_GOV_LENGTH in self._config[CONFIG_VIDEO_ENCODER]:
                        mpeg4_config["GovLength"] = self._config[CONFIG_VIDEO_ENCODER][
                            CONFIG_VIDEO_GOV_LENGTH
                        ]

                set_video_encoder_config = await self.set_video_encoder_configuration(
                    video_config, video_force_persistence
                )

            # ---- Audio Encoder config ----

            if CONFIG_AUDIO_ENCODER in self._config:
                audio_force_persistence = self._config[CONFIG_AUDIO_ENCODER].get(
                    CONFIG_AUDIO_FORCE_PERSISTENCE, DEFAULT_AUDIO_FORCE_PERSISTENCE
                )

                audio_config = {
                    "token": self._selected_profile.AudioEncoderConfiguration.token,
                    "Name": self._selected_profile.AudioEncoderConfiguration.Name,
                    "Encoding": self._config[CONFIG_AUDIO_ENCODER][
                        CONFIG_AUDIO_ENCODING
                    ],
                }

                if CONFIG_AUDIO_BITRATE in self._config[CONFIG_AUDIO_ENCODER]:
                    audio_config["Bitrate"] = self._config[CONFIG_AUDIO_ENCODER][
                        CONFIG_AUDIO_BITRATE
                    ]

                if CONFIG_AUDIO_SAMPLE_RATE in self._config[CONFIG_AUDIO_ENCODER]:
                    audio_config["SampleRate"] = self._config[CONFIG_AUDIO_ENCODER][
                        CONFIG_AUDIO_SAMPLE_RATE
                    ]

                set_audio_encoder_config = await self.set_audio_encoder_configuration(
                    audio_config, audio_force_persistence
                )

            if set_video_encoder_config or set_audio_encoder_config:
                LOGGER.info(
                    f"Media service configuration for {self._camera.identifier} "
                    f"has been applied."
                )
                return True

            LOGGER.error(
                f"Error applying Media service configuration for "
                f"{self._camera.identifier}!"
            )
            return False
        except (ValueError, AttributeError) as error:
            LOGGER.error(
                f"Error applying Media service configuration for "
                f"{self._camera.identifier}: {error}"
            )
            return False
