"""Viseron types."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import voluptuous as vol
    from sklearn.neighbors import KNeighborsClassifier

    from viseron.components import Component
    from viseron.components.compreface.face_recognition import CompreFaceService
    from viseron.components.darknet import BaseDarknet
    from viseron.components.data_stream import DataStream
    from viseron.components.discord import DiscordNotifier
    from viseron.components.edgetpu.edgetpu_types import EdgeTPUViseronData
    from viseron.components.go2rtc import Go2RTC
    from viseron.components.gotify import GotifyEventNotifier
    from viseron.components.hailo import Hailo8Detector
    from viseron.components.logger.logger_types import LoggerViseronData
    from viseron.components.mqtt import MQTT
    from viseron.components.nvr.nvr import NVR
    from viseron.components.ptz import PTZ
    from viseron.components.storage import Storage
    from viseron.components.telegram.ptz_control import TelegramPTZ
    from viseron.components.webserver import Webserver
    from viseron.components.webserver.download_token import DownloadToken
    from viseron.components.webserver.public_image_token import PublicImageToken
    from viseron.components.webserver.websocket_api import WebSocketHandler


class ViseronData(TypedDict, total=False):
    """TypedDict for Viseron data storage.

    If a component saves anything to vis.data, it is REQUIRED to be typed here.
    When mypy adds support for TypedDict with extra_items, this can be changed to
    optional.

    Note that the type hint for vis.data has not been changed to ViseronData yet,
    to not break existing components. Once all components have been updated to
    include their data here, the type hint for vis.data can be changed.
    """

    # Viseron core
    loading: dict[str, Component]
    loaded: dict[str, Component]
    failed: dict[str, Component]

    # Viseron core components
    data_stream: DataStream
    logger: LoggerViseronData
    storage: Storage
    webserver: Webserver
    websocket_commands: dict[
        str, tuple[Callable[[WebSocketHandler, dict], Awaitable[None]], vol.Schema]
    ]
    websocket_connections: list[WebSocketHandler]
    download_tokens: dict[str, DownloadToken]
    public_image_tokens: dict[str, PublicImageToken]

    # Components
    compreface: dict[Literal["face_recognition"], CompreFaceService]
    darknet: BaseDarknet
    dlib: dict[Literal["classifier"], KNeighborsClassifier | None]
    discord: DiscordNotifier
    edgetpu: EdgeTPUViseronData
    go2rtc: Go2RTC
    gotify: GotifyEventNotifier
    hailo: Hailo8Detector
    mqtt: MQTT
    nvr: dict[str, NVR]
    telegram: TelegramPTZ
    ptz: PTZ


SupportedDomains = Literal[
    "camera",
    "face_recognition",
    "image_classification",
    "license_plate_recognition",
    "motion_detector",
    "nvr",
    "object_detector",
]


class Domain(str, enum.Enum):
    """Domains."""

    CAMERA = "camera"
    FACE_RECOGNITION = "face_recognition"
    IMAGE_CLASSIFICATION = "image_classification"
    LICENSE_PLATE_RECOGNITION = "license_plate_recognition"
    MOTION_DETECTOR = "motion_detector"
    NVR = "nvr"
    OBJECT_DETECTOR = "object_detector"

    @classmethod
    def post_processors(
        cls,
    ) -> tuple[
        Literal[Domain.FACE_RECOGNITION],
        Literal[Domain.IMAGE_CLASSIFICATION],
        Literal[Domain.LICENSE_PLATE_RECOGNITION],
    ]:
        """Return post processors."""
        return (
            cls.FACE_RECOGNITION,
            cls.IMAGE_CLASSIFICATION,
            cls.LICENSE_PLATE_RECOGNITION,
        )


class SnapshotDomain(enum.Enum):
    """Snapshot domains."""

    FACE_RECOGNITION = "face_recognition"
    LICENSE_PLATE_RECOGNITION = "license_plate_recognition"
    MOTION_DETECTOR = "motion_detector"
    OBJECT_DETECTOR = "object_detector"


DatabaseOperations = Literal["insert", "update", "delete"]
