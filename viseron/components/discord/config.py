"""Config of the discord component."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, SecretStr

from viseron.helpers.config_model import ComponentRoot, ConfigModel
from viseron.helpers.config_types import CameraIdentifier, NoneToDict

from .const import (
    DEFAULT_DETECTION_LABELS,
    DEFAULT_MAX_VIDEO_SIZE_MB,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DETECTION_LABEL,
    DESC_DETECTION_LABELS,
    DESC_DISCORD_WEBHOOK_URL,
    DESC_MAX_VIDEO_SIZE_MB,
    DESC_SEND_THUMBNAIL,
    DESC_SEND_VIDEO,
)


class DiscordCameraConfig(ConfigModel):
    """Config of a camera. A key that is not set falls back to the global config."""

    webhook_url: SecretStr | None = Field(
        default=None, description=DESC_DISCORD_WEBHOOK_URL
    )
    detection_label: str | None = Field(
        default=None, deprecated=True, description=DESC_DETECTION_LABEL
    )
    detection_labels: list[str] | None = Field(
        default=None, description=DESC_DETECTION_LABELS
    )
    send_detection_thumbnail: bool | None = Field(
        default=None, description=DESC_SEND_THUMBNAIL
    )
    send_detection_video: bool | None = Field(default=None, description=DESC_SEND_VIDEO)
    max_video_size_mb: int | None = Field(
        default=None, description=DESC_MAX_VIDEO_SIZE_MB
    )


class DiscordConfig(ConfigModel):
    """Config of the discord component."""

    webhook_url: SecretStr = Field(description=DESC_DISCORD_WEBHOOK_URL)
    detection_label: str | None = Field(
        default=None, deprecated=True, description=DESC_DETECTION_LABEL
    )
    detection_labels: list[str] = Field(
        default=DEFAULT_DETECTION_LABELS, description=DESC_DETECTION_LABELS
    )
    send_detection_thumbnail: bool = Field(
        default=True, description=DESC_SEND_THUMBNAIL
    )
    send_detection_video: bool = Field(default=True, description=DESC_SEND_VIDEO)
    max_video_size_mb: int = Field(
        default=DEFAULT_MAX_VIDEO_SIZE_MB, description=DESC_MAX_VIDEO_SIZE_MB
    )
    cameras: dict[CameraIdentifier, Annotated[DiscordCameraConfig, NoneToDict]] = Field(
        description=DESC_CAMERAS
    )


class DiscordRoot(ComponentRoot):
    """Config with the discord component at the root."""

    discord: DiscordConfig = Field(description=DESC_COMPONENT)
