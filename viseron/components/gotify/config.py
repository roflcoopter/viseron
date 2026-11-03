"""Config of the gotify component."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, SecretStr

from viseron.helpers.config_model import ComponentRoot, ConfigModel
from viseron.helpers.config_types import CameraIdentifier, NoneToDict

from .const import (
    DEFAULT_DETECTION_LABEL,
    DEFAULT_IMAGE_MAX_SIZE,
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_PRIORITY,
    DESC_CAMERA_DETECTION_LABEL,
    DESC_CAMERA_SEND_THUMBNAIL,
    DESC_CAMERA_USE_PUBLIC_URL,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DETECTION_LABEL,
    DESC_GOTIFY_PRIORITY,
    DESC_GOTIFY_TOKEN,
    DESC_GOTIFY_URL,
    DESC_IMAGE_MAX_SIZE,
    DESC_IMAGE_QUALITY,
    DESC_SEND_THUMBNAIL,
    DESC_USE_PUBLIC_URL,
)


class GotifyCameraConfig(ConfigModel):
    """Config of a camera. A key that is not set falls back to the gotify config."""

    detection_label: str | None = Field(
        default=None, description=DESC_CAMERA_DETECTION_LABEL
    )
    send_thumbnail: bool | None = Field(
        default=None, description=DESC_CAMERA_SEND_THUMBNAIL
    )
    use_public_url: bool | None = Field(
        default=None, description=DESC_CAMERA_USE_PUBLIC_URL
    )


class GotifyConfig(ConfigModel):
    """Config of the gotify component."""

    gotify_url: str = Field(description=DESC_GOTIFY_URL)
    gotify_token: SecretStr = Field(description=DESC_GOTIFY_TOKEN)
    priority: int = Field(
        default=DEFAULT_PRIORITY, ge=1, le=10, description=DESC_GOTIFY_PRIORITY
    )
    detection_label: str = Field(
        default=DEFAULT_DETECTION_LABEL, description=DESC_DETECTION_LABEL
    )
    send_thumbnail: bool = Field(default=False, description=DESC_SEND_THUMBNAIL)
    use_public_url: bool = Field(default=False, description=DESC_USE_PUBLIC_URL)
    image_max_size: int = Field(
        default=DEFAULT_IMAGE_MAX_SIZE, ge=0, le=7680, description=DESC_IMAGE_MAX_SIZE
    )
    image_quality: int = Field(
        default=DEFAULT_IMAGE_QUALITY, ge=1, le=100, description=DESC_IMAGE_QUALITY
    )
    cameras: dict[CameraIdentifier, Annotated[GotifyCameraConfig, NoneToDict]] = Field(
        description=DESC_CAMERAS
    )


class GotifyRoot(ComponentRoot):
    """Config with the gotify component at the root."""

    gotify: GotifyConfig = Field(description=DESC_COMPONENT)
