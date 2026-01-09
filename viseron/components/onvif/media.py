"""Media service management for ONVIF component."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from onvif import ONVIFClient

from .utils import operation

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
        self._profiles: list[Any] = []

    async def initialize(self) -> None:
        """Initialize the Media service."""
        self._media_service = self._client.media()

        # Load media profiles
        self._profiles = await self.get_profiles()

        if not self._auto_config and self._config:
            await self.apply_config()

    # ## The Real Operations ## #

    @operation()
    async def get_profiles(self) -> Any:
        """Get media profiles."""
        return self._media_service.GetProfiles()

    @operation()
    async def get_profile(self, profile_token: str) -> Any:
        """Get a specific media profile."""
        return self._media_service.GetProfile(ProfileToken=profile_token)

    @operation()
    async def get_stream_uri(
        self, profile_token: str | None = None, stream_type: str = "RTP-Unicast"
    ) -> Any:
        """Get stream URI for a profile."""
        stream_setup = {"Stream": stream_type, "Transport": {"Protocol": "RTSP"}}
        return self._media_service.GetStreamUri(
            StreamSetup=stream_setup, ProfileToken=profile_token
        )

    @operation()
    async def get_snapshot_uri(self, profile_token: str | None = None) -> Any:
        """Get snapshot URI for a profile."""
        return self._media_service.GetSnapshotUri(ProfileToken=profile_token)

    @operation()
    async def get_video_sources(self) -> Any:
        """Get available video sources."""
        return self._media_service.GetVideoSources()

    @operation()
    async def get_video_source_configurations(self) -> Any:
        """Get video source configurations."""
        return self._media_service.GetVideoSourceConfigurations()

    @operation()
    async def get_video_encoder_configurations(self) -> Any:
        """Get video encoder configurations."""
        return self._media_service.GetVideoEncoderConfigurations()

    @operation()
    async def get_audio_sources(self) -> Any:
        """Get available audio sources."""
        return self._media_service.GetAudioSources()

    @operation()
    async def get_audio_source_configurations(self) -> Any:
        """Get audio source configurations."""
        return self._media_service.GetAudioSourceConfigurations()

    @operation()
    async def get_audio_encoder_configurations(self) -> Any:
        """Get audio encoder configurations."""
        return self._media_service.GetAudioEncoderConfigurations()

    @operation()
    async def set_video_encoder_configuration(
        self, configuration: dict[str, Any], force_persistence: bool = True
    ) -> bool:
        """Set video encoder configuration for a profile."""
        self._media_service.SetVideoEncoderConfiguration(
            Configuration=configuration, ForcePersistence=force_persistence
        )

        return True

    @operation()
    async def set_video_source_configuration(
        self, configuration: dict[str, Any], force_persistence: bool = True
    ) -> bool:
        """Set video source configuration for a profile."""
        self._media_service.SetVideoSourceConfiguration(
            Configuration=configuration, ForcePersistence=force_persistence
        )

        return True

    @operation()
    async def create_profile(self, name: str, token: str | None = None) -> Any:
        """Create a new media profile."""
        return self._media_service.CreateProfile(Name=name, Token=token)

    @operation()
    async def delete_profile(self, profile_token: str) -> bool:
        """Delete a media profile."""
        self._media_service.DeleteProfile(ProfileToken=profile_token)

        return True

    # ## Profile Accessors ## #

    def get_cached_profiles(self):
        """Get cached media profiles without making ONVIF call."""
        return self._profiles

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
        return True
