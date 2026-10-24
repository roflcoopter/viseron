"""Config of the telegram component."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, SecretStr

from viseron.helpers.config_model import ComponentRoot, ConfigModel
from viseron.helpers.config_types import CameraIdentifier, NoneToDict

from .const import (
    DEFAULT_DETECTION_LABELS,
    DEFAULT_SEND_MESSAGE,
    DEFAULT_SEND_THUMBNAIL,
    DEFAULT_SEND_VIDEO,
    DEFAULT_TELEGRAM_LOG_IDS,
    DEFAULT_TELEGRAM_USER_IDS,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DETECTION_LABEL,
    DESC_DETECTION_LABELS,
    DESC_SEND_MESSAGE,
    DESC_SEND_THUMBNAIL,
    DESC_SEND_VIDEO,
    DESC_TELEGRAM_BOT_TOKEN,
    DESC_TELEGRAM_CHAT_IDS,
    DESC_TELEGRAM_LOG_IDS,
    DESC_TELEGRAM_USER_IDS,
)


class TelegramCameraConfig(ConfigModel):
    """Config of a camera. A key that is not set falls back to the telegram config."""

    detection_label: str | None = Field(
        default=None, deprecated=True, description=DESC_DETECTION_LABEL
    )
    detection_labels: list[str] | None = Field(
        default=None, description=DESC_DETECTION_LABELS
    )


class TelegramConfig(ConfigModel):
    """Config of the telegram component."""

    telegram_bot_token: SecretStr = Field(description=DESC_TELEGRAM_BOT_TOKEN)
    telegram_chat_ids: list[int] = Field(description=DESC_TELEGRAM_CHAT_IDS)
    telegram_user_ids: list[int] = Field(
        default=DEFAULT_TELEGRAM_USER_IDS, description=DESC_TELEGRAM_USER_IDS
    )
    detection_label: str | None = Field(
        default=None, deprecated=True, description=DESC_DETECTION_LABEL
    )
    detection_labels: list[str] = Field(
        default=DEFAULT_DETECTION_LABELS, description=DESC_DETECTION_LABELS
    )
    send_detection_thumbnail: bool = Field(
        default=DEFAULT_SEND_THUMBNAIL, description=DESC_SEND_THUMBNAIL
    )
    send_detection_video: bool = Field(
        default=DEFAULT_SEND_VIDEO, description=DESC_SEND_VIDEO
    )
    send_detection_message: bool = Field(
        default=DEFAULT_SEND_MESSAGE, description=DESC_SEND_MESSAGE
    )
    telegram_log_ids: bool = Field(
        default=DEFAULT_TELEGRAM_LOG_IDS, description=DESC_TELEGRAM_LOG_IDS
    )
    cameras: dict[CameraIdentifier, Annotated[TelegramCameraConfig, NoneToDict]] = (
        Field(description=DESC_CAMERAS)
    )


class TelegramRoot(ComponentRoot):
    """Config with the telegram component at the root."""

    telegram: TelegramConfig = Field(description=DESC_COMPONENT)
