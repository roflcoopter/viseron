"""ONVIF component."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import voluptuous as vol
from onvif import ONVIFClient

from viseron.const import EVENT_DOMAIN_REGISTERED, VISERON_SIGNAL_STOPPING
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.helpers import escape_string
from viseron.helpers.logs import SensitiveInformationFilter
from viseron.helpers.validators import CameraIdentifier
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    AUDIO_ENCODING_MAP,
    COMPONENT,
    CONFIG_AUDIO_BITRATE,
    CONFIG_AUDIO_ENCODER,
    CONFIG_AUDIO_ENCODING,
    CONFIG_AUDIO_FORCE_PERSISTENCE,
    CONFIG_AUDIO_SAMPLE_RATE,
    CONFIG_CAMERAS,
    CONFIG_DEVICE,
    CONFIG_DEVICE_DATETIME_TYPE,
    CONFIG_DEVICE_DAYLIGHT_SAVINGS,
    CONFIG_DEVICE_DISCOVERABLE,
    CONFIG_DEVICE_HOSTNAME,
    CONFIG_DEVICE_NTP_FROM_DHCP,
    CONFIG_DEVICE_NTP_SERVER,
    CONFIG_DEVICE_NTP_TYPE,
    CONFIG_DEVICE_TIMEZONE,
    CONFIG_HOST,
    CONFIG_IMAGING,
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
    CONFIG_MEDIA,
    CONFIG_ONVIF_AUTO_CONFIG,
    CONFIG_ONVIF_PASSWORD,
    CONFIG_ONVIF_PORT,
    CONFIG_ONVIF_TIMEOUT,
    CONFIG_ONVIF_USE_HTTPS,
    CONFIG_ONVIF_USERNAME,
    CONFIG_ONVIF_VERIFY_SSL,
    CONFIG_ONVIF_WSDL_DIR,
    CONFIG_PTZ,
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
    DEFAULT_IMAGING_FORCE_PERSISTENCE,
    DEFAULT_ONVIF_AUTO_CONFIG,
    DEFAULT_ONVIF_TIMEOUT,
    DEFAULT_ONVIF_USE_HTTPS,
    DEFAULT_ONVIF_VERIFY_SSL,
    DEFAULT_PTZ_HOME_POSITION,
    DEFAULT_PTZ_PRESET_ON_STARTUP,
    DEFAULT_PTZ_REVERSE_PAN,
    DEFAULT_PTZ_REVERSE_TILT,
    DEFAULT_VIDEO_FORCE_PERSISTENCE,
    DESC_AUDIO_BITRATE,
    DESC_AUDIO_ENCODER,
    DESC_AUDIO_ENCODING,
    DESC_AUDIO_FORCE_PERSISTENCE,
    DESC_AUDIO_SAMPLE_RATE,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DEVICE,
    DESC_DEVICE_DATETIME_TYPE,
    DESC_DEVICE_DAYLIGHT_SAVINGS,
    DESC_DEVICE_DISCOVERABLE,
    DESC_DEVICE_HOSTNAME,
    DESC_DEVICE_NTP_FROM_DHCP,
    DESC_DEVICE_NTP_SERVER,
    DESC_DEVICE_NTP_TYPE,
    DESC_DEVICE_TIMEZONE,
    DESC_IMAGING,
    DESC_IMAGING_BACKLIGHT_COMPENSATION,
    DESC_IMAGING_BRIGHTNESS,
    DESC_IMAGING_COLOR_SATURATION,
    DESC_IMAGING_CONTRAST,
    DESC_IMAGING_DEFOGGING,
    DESC_IMAGING_EXPOSURE,
    DESC_IMAGING_FOCUS,
    DESC_IMAGING_FORCE_PERSISTENCE,
    DESC_IMAGING_IMAGE_STABILIZATION,
    DESC_IMAGING_IRCUT_FILTER,
    DESC_IMAGING_IRCUT_FILTER_AUTO_ADJUSTMENT,
    DESC_IMAGING_NOISE_REDUCTION,
    DESC_IMAGING_SHARPNESS,
    DESC_IMAGING_TONE_COMPENSATION,
    DESC_IMAGING_WHITE_BALANCE,
    DESC_IMAGING_WIDE_DYNAMIC_RANGE,
    DESC_MEDIA,
    DESC_ONVIF_AUTO_CONFIG,
    DESC_ONVIF_PASSWORD,
    DESC_ONVIF_PORT,
    DESC_ONVIF_TIMEOUT,
    DESC_ONVIF_USE_HTTPS,
    DESC_ONVIF_USERNAME,
    DESC_ONVIF_VERIFY_SSL,
    DESC_ONVIF_WSDL_DIR,
    DESC_PTZ,
    DESC_PTZ_HOME_POSITION,
    DESC_PTZ_MAX_PAN,
    DESC_PTZ_MAX_TILT,
    DESC_PTZ_MAX_ZOOM,
    DESC_PTZ_MIN_PAN,
    DESC_PTZ_MIN_TILT,
    DESC_PTZ_MIN_ZOOM,
    DESC_PTZ_PRESET_NAME,
    DESC_PTZ_PRESET_ON_STARTUP,
    DESC_PTZ_PRESET_PAN,
    DESC_PTZ_PRESET_TILT,
    DESC_PTZ_PRESET_ZOOM,
    DESC_PTZ_PRESETS,
    DESC_PTZ_REVERSE_PAN,
    DESC_PTZ_REVERSE_TILT,
    DESC_VIDEO_BITRATE,
    DESC_VIDEO_ENCODER,
    DESC_VIDEO_ENCODING,
    DESC_VIDEO_ENCODING_INTERVAL,
    DESC_VIDEO_FORCE_PERSISTENCE,
    DESC_VIDEO_FRAME_RATE,
    DESC_VIDEO_GOV_LENGTH,
    DESC_VIDEO_H264,
    DESC_VIDEO_MPEG4,
    DESC_VIDEO_QUALITY,
    DESC_VIDEO_RESOLUTION,
    DESC_VIDEO_RESOLUTION_HEIGHT,
    DESC_VIDEO_RESOLUTION_WIDTH,
    DEVICE_DATETIME_TYPE_MAP,
    DEVICE_NTP_TYPE_MAP,
    IMAGING_BACKLIGHT_COMPENSATION_MAP,
    IMAGING_IRCUT_FILTER_MAP,
    VIDEO_ENCODING_MAP,
    VIDEO_H264_MAP,
    VIDEO_MPEG4_MAP,
)
from .device import Device
from .imaging import Imaging
from .media import Media
from .ptz import PTZ
from .utils import extract_rtsp_from_go2rtc

if TYPE_CHECKING:
    from viseron import Event, Viseron

LOGGER = logging.getLogger(__name__)

# Device Service Schema
DEVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_DEVICE_HOSTNAME,
            description=DESC_DEVICE_HOSTNAME,
        ): str,
        vol.Optional(
            CONFIG_DEVICE_DISCOVERABLE,
            description=DESC_DEVICE_DISCOVERABLE,
        ): bool,
        vol.Optional(
            CONFIG_DEVICE_DATETIME_TYPE,
            description=DESC_DEVICE_DATETIME_TYPE,
        ): vol.In(DEVICE_DATETIME_TYPE_MAP),
        vol.Optional(
            CONFIG_DEVICE_DAYLIGHT_SAVINGS,
            description=DESC_DEVICE_DAYLIGHT_SAVINGS,
        ): bool,
        vol.Optional(
            CONFIG_DEVICE_TIMEZONE,
            description=DESC_DEVICE_TIMEZONE,
        ): str,
        vol.Optional(
            CONFIG_DEVICE_NTP_FROM_DHCP,
            description=DESC_DEVICE_NTP_FROM_DHCP,
        ): bool,
        vol.Optional(
            CONFIG_DEVICE_NTP_TYPE,
            description=DESC_DEVICE_NTP_TYPE,
        ): vol.In(DEVICE_NTP_TYPE_MAP),
        vol.Optional(
            CONFIG_DEVICE_NTP_SERVER,
            description=DESC_DEVICE_NTP_SERVER,
        ): str,
    }
)

# Video Encoder for Media Schema
VIDEO_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_VIDEO_FORCE_PERSISTENCE,
            description=DESC_VIDEO_FORCE_PERSISTENCE,
            default=DEFAULT_VIDEO_FORCE_PERSISTENCE,
        ): bool,
        vol.Required(
            CONFIG_VIDEO_ENCODING,
            description=DESC_VIDEO_ENCODING,
        ): vol.In(VIDEO_ENCODING_MAP),
        vol.Optional(
            CONFIG_VIDEO_MPEG4,
            description=DESC_VIDEO_MPEG4,
        ): vol.In(VIDEO_MPEG4_MAP),
        vol.Optional(
            CONFIG_VIDEO_H264,
            description=DESC_VIDEO_H264,
        ): vol.In(VIDEO_H264_MAP),
        vol.Required(
            CONFIG_VIDEO_RESOLUTION,
            description=DESC_VIDEO_RESOLUTION,
        ): vol.Schema(
            {
                vol.Required(
                    CONFIG_VIDEO_RESOLUTION_WIDTH,
                    description=DESC_VIDEO_RESOLUTION_WIDTH,
                ): int,
                vol.Required(
                    CONFIG_VIDEO_RESOLUTION_HEIGHT,
                    description=DESC_VIDEO_RESOLUTION_HEIGHT,
                ): int,
            }
        ),
        vol.Optional(
            CONFIG_VIDEO_QUALITY,
            description=DESC_VIDEO_QUALITY,
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_VIDEO_FRAME_RATE,
            description=DESC_VIDEO_FRAME_RATE,
        ): int,
        vol.Optional(
            CONFIG_VIDEO_ENCODING_INTERVAL,
            description=DESC_VIDEO_ENCODING_INTERVAL,
        ): int,
        vol.Optional(
            CONFIG_VIDEO_BITRATE,
            description=DESC_VIDEO_BITRATE,
        ): int,
        vol.Optional(
            CONFIG_VIDEO_GOV_LENGTH,
            description=DESC_VIDEO_GOV_LENGTH,
        ): int,
    }
)

# Audio Encoder for Media Schema
AUDIO_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_AUDIO_FORCE_PERSISTENCE,
            description=DESC_AUDIO_FORCE_PERSISTENCE,
            default=DEFAULT_AUDIO_FORCE_PERSISTENCE,
        ): bool,
        vol.Required(
            CONFIG_AUDIO_ENCODING,
            description=DESC_AUDIO_ENCODING,
        ): vol.In(AUDIO_ENCODING_MAP),
        vol.Optional(
            CONFIG_AUDIO_BITRATE,
            description=DESC_AUDIO_BITRATE,
        ): int,
        vol.Optional(
            CONFIG_AUDIO_SAMPLE_RATE,
            description=DESC_AUDIO_SAMPLE_RATE,
        ): int,
    }
)

# Media Service Schema
MEDIA_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_VIDEO_ENCODER, description=DESC_VIDEO_ENCODER
        ): VIDEO_SCHEMA,
        vol.Optional(
            CONFIG_AUDIO_ENCODER, description=DESC_AUDIO_ENCODER
        ): AUDIO_SCHEMA,
    }
)

# Imaging Service Schema
IMAGING_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_IMAGING_FORCE_PERSISTENCE,
            description=DESC_IMAGING_FORCE_PERSISTENCE,
            default=DEFAULT_IMAGING_FORCE_PERSISTENCE,
        ): bool,
        vol.Optional(
            CONFIG_IMAGING_BRIGHTNESS,
            description=DESC_IMAGING_BRIGHTNESS,
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_IMAGING_COLOR_SATURATION,
            description=DESC_IMAGING_COLOR_SATURATION,
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_IMAGING_CONTRAST,
            description=DESC_IMAGING_CONTRAST,
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_IMAGING_SHARPNESS,
            description=DESC_IMAGING_SHARPNESS,
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_IMAGING_IRCUT_FILTER,
            description=DESC_IMAGING_IRCUT_FILTER,
        ): vol.In(IMAGING_IRCUT_FILTER_MAP),
        vol.Optional(
            CONFIG_IMAGING_BACKLIGHT_COMPENSATION,
            description=DESC_IMAGING_BACKLIGHT_COMPENSATION,
        ): vol.In(IMAGING_BACKLIGHT_COMPENSATION_MAP),
        vol.Optional(
            CONFIG_IMAGING_EXPOSURE,
            description=DESC_IMAGING_EXPOSURE,
        ): dict,
        vol.Optional(
            CONFIG_IMAGING_FOCUS,
            description=DESC_IMAGING_FOCUS,
        ): dict,
        vol.Optional(
            CONFIG_IMAGING_WIDE_DYNAMIC_RANGE,
            description=DESC_IMAGING_WIDE_DYNAMIC_RANGE,
        ): dict,
        vol.Optional(
            CONFIG_IMAGING_WHITE_BALANCE,
            description=DESC_IMAGING_WHITE_BALANCE,
        ): dict,
        vol.Optional(
            CONFIG_IMAGING_IMAGE_STABILIZATION,
            description=DESC_IMAGING_IMAGE_STABILIZATION,
        ): dict,
        vol.Optional(
            CONFIG_IMAGING_IRCUT_FILTER_AUTO_ADJUSTMENT,
            description=DESC_IMAGING_IRCUT_FILTER_AUTO_ADJUSTMENT,
        ): dict,
        vol.Optional(
            CONFIG_IMAGING_TONE_COMPENSATION,
            description=DESC_IMAGING_TONE_COMPENSATION,
        ): dict,
        vol.Optional(
            CONFIG_IMAGING_DEFOGGING,
            description=DESC_IMAGING_DEFOGGING,
        ): dict,
        vol.Optional(
            CONFIG_IMAGING_NOISE_REDUCTION,
            description=DESC_IMAGING_NOISE_REDUCTION,
        ): dict,
    }
)

# PTZ Preset Schema
PRESET_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_PTZ_PRESET_NAME, description=DESC_PTZ_PRESET_NAME): str,
        vol.Required(
            CONFIG_PTZ_PRESET_PAN, description=DESC_PTZ_PRESET_PAN
        ): vol.Coerce(float),
        vol.Required(
            CONFIG_PTZ_PRESET_TILT, description=DESC_PTZ_PRESET_TILT
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_PTZ_PRESET_ZOOM, description=DESC_PTZ_PRESET_ZOOM
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_PTZ_PRESET_ON_STARTUP,
            description=DESC_PTZ_PRESET_ON_STARTUP,
            default=DEFAULT_PTZ_PRESET_ON_STARTUP,
        ): bool,
    }
)

# PTZ Service Schema
PTZ_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_PTZ_HOME_POSITION,
            description=DESC_PTZ_HOME_POSITION,
            default=DEFAULT_PTZ_HOME_POSITION,
        ): bool,
        vol.Optional(
            CONFIG_PTZ_REVERSE_PAN,
            description=DESC_PTZ_REVERSE_PAN,
            default=DEFAULT_PTZ_REVERSE_PAN,
        ): bool,
        vol.Optional(
            CONFIG_PTZ_REVERSE_TILT,
            description=DESC_PTZ_REVERSE_TILT,
            default=DEFAULT_PTZ_REVERSE_TILT,
        ): bool,
        vol.Optional(
            CONFIG_PTZ_MIN_PAN,
            description=DESC_PTZ_MIN_PAN,
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_PTZ_MAX_PAN,
            description=DESC_PTZ_MAX_PAN,
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_PTZ_MIN_TILT,
            description=DESC_PTZ_MIN_TILT,
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_PTZ_MAX_TILT,
            description=DESC_PTZ_MAX_TILT,
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_PTZ_MIN_ZOOM,
            description=DESC_PTZ_MIN_ZOOM,
        ): vol.Coerce(float),
        vol.Optional(
            CONFIG_PTZ_MAX_ZOOM,
            description=DESC_PTZ_MAX_ZOOM,
        ): vol.Coerce(float),
        vol.Optional(CONFIG_PTZ_PRESETS, description=DESC_PTZ_PRESETS): [PRESET_SCHEMA],
    }
)

# Camera Schema with all service configurations
CAMERA_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_ONVIF_PORT, description=DESC_ONVIF_PORT): int,
        vol.Required(CONFIG_ONVIF_USERNAME, description=DESC_ONVIF_USERNAME): str,
        vol.Required(CONFIG_ONVIF_PASSWORD, description=DESC_ONVIF_PASSWORD): str,
        vol.Optional(
            CONFIG_ONVIF_TIMEOUT,
            description=DESC_ONVIF_TIMEOUT,
            default=DEFAULT_ONVIF_TIMEOUT,
        ): int,
        vol.Optional(
            CONFIG_ONVIF_USE_HTTPS,
            description=DESC_ONVIF_USE_HTTPS,
            default=DEFAULT_ONVIF_USE_HTTPS,
        ): bool,
        vol.Optional(
            CONFIG_ONVIF_VERIFY_SSL,
            description=DESC_ONVIF_VERIFY_SSL,
            default=DEFAULT_ONVIF_VERIFY_SSL,
        ): bool,
        vol.Optional(
            CONFIG_ONVIF_WSDL_DIR,
            description=DESC_ONVIF_WSDL_DIR,
        ): str,
        vol.Optional(
            CONFIG_ONVIF_AUTO_CONFIG,
            description=DESC_ONVIF_AUTO_CONFIG,
            default=DEFAULT_ONVIF_AUTO_CONFIG,
        ): bool,
        vol.Optional(CONFIG_DEVICE, description=DESC_DEVICE): DEVICE_SCHEMA,
        vol.Optional(CONFIG_MEDIA, description=DESC_MEDIA): MEDIA_SCHEMA,
        vol.Optional(CONFIG_IMAGING, description=DESC_IMAGING): IMAGING_SCHEMA,
        vol.Optional(CONFIG_PTZ, description=DESC_PTZ): PTZ_SCHEMA,
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
    """Set up the ONVIF component."""
    onvif = ONVIF(vis, config[COMPONENT])
    RestartableThread(
        target=onvif.run,
        name=config[COMPONENT],
    ).start()
    return True


class ONVIF:
    """ONVIF Controller manages ONVIF services for cameras."""

    def __init__(self, vis: Viseron, config) -> None:
        self._vis = vis
        self._config = config
        for cam_name in self._config[CONFIG_CAMERAS]:
            camera = self._config[CONFIG_CAMERAS][cam_name]
            if camera.get(CONFIG_ONVIF_PASSWORD):
                SensitiveInformationFilter.add_sensitive_string(
                    camera[CONFIG_ONVIF_PASSWORD]
                )
                SensitiveInformationFilter.add_sensitive_string(
                    escape_string(camera[CONFIG_ONVIF_PASSWORD])
                )
        self._cameras: dict[str, AbstractCamera] = {}
        self._onvif_clients: dict[str, ONVIFClient] = {}
        self._device_services: dict[str, Device] = {}
        self._imaging_services: dict[str, Imaging] = {}
        self._media_services: dict[str, Media] = {}
        self._ptz_services: dict[str, PTZ] = {}
        self._register_lock: asyncio.Lock = asyncio.Lock()
        self._stop_event: asyncio.Event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        vis.data[COMPONENT] = self

    def initialize(self):
        """Initialize ONVIF Controller."""
        self._vis.register_signal_handler(VISERON_SIGNAL_STOPPING, self.shutdown)
        self._vis.listen_event(
            EVENT_DOMAIN_REGISTERED.format(domain=CAMERA_DOMAIN),
            self._camera_registered,
        )

    def run(self):
        """Run ONVIF Controller."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._run())
        LOGGER.info("ONVIF Controller done")

    async def _run(self):
        """Async Run ONVIF Controller."""
        self._loop = asyncio.get_event_loop()
        self.initialize()
        while not self._stop_event.is_set():
            await asyncio.sleep(0.1)

    def shutdown(self):
        """Shutdown ONVIF Controller."""
        # For now the implementation only to stop any patrol events
        LOGGER.info("Stopping ONVIF Controller")
        for ptz_service in self._ptz_services.values():
            ptz_service.stop_patrol()
        self._stop_event.set()

    def _camera_registered(self, event: Event[AbstractCamera]) -> None:
        """Handle camera registration event."""
        camera: AbstractCamera = event.data
        LOGGER.debug(f"Camera registered event received for {camera.identifier}")

        if camera.identifier in self._config[CONFIG_CAMERAS]:
            LOGGER.debug(f"Processing ONVIF setup for camera {camera.identifier}")
            self._cameras[camera.identifier] = camera
            config = self._config[CONFIG_CAMERAS][camera.identifier]

            # Determine the host to use for ONVIF client
            onvif_host = camera.config[CONFIG_HOST]
            LOGGER.debug(f"Initial ONVIF host for {camera.identifier}: {onvif_host}")

            # Try to extract host from go2rtc RTSP URL if component available
            rtsp_url = extract_rtsp_from_go2rtc(camera)
            if rtsp_url:
                try:
                    parsed_url = urlparse(rtsp_url)
                    if parsed_url.hostname:
                        onvif_host = parsed_url.hostname
                except (ValueError, AttributeError) as error:
                    LOGGER.warning(
                        f"Could not parse host from go2rtc RTSP URL: {error}. "
                        f"Using camera config host instead."
                    )
            else:
                LOGGER.debug(
                    f"No RTSP URL found from go2rtc for {camera.identifier}, "
                    f"using camera config host: {onvif_host}"
                )

            # Create ONVIF client
            onvif_client = ONVIFClient(
                onvif_host,
                config.get(CONFIG_ONVIF_PORT),
                config.get(CONFIG_ONVIF_USERNAME),
                config.get(CONFIG_ONVIF_PASSWORD),
                timeout=config.get(CONFIG_ONVIF_TIMEOUT),
                use_https=config.get(CONFIG_ONVIF_USE_HTTPS),
                verify_ssl=config.get(CONFIG_ONVIF_VERIFY_SSL),
                wsdl_dir=config.get(CONFIG_ONVIF_WSDL_DIR),
            )
            self._onvif_clients[camera.identifier] = onvif_client

            # Then initialize all ONVIF services!
            self._initialize_camera_services(camera, onvif_client, config)

    def _initialize_camera_services(
        self, camera: AbstractCamera, client: ONVIFClient, config: dict[str, Any]
    ):
        """
        Initialize ONVIF services for a camera.

        All services share the same ONVIFClient instance to avoid redundant connections.
        And will use asyncio to initialize services concurrently.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        auto_config = config.get(CONFIG_ONVIF_AUTO_CONFIG, True)

        async def init_device():
            try:
                device_config = config.get(CONFIG_DEVICE, {})
                device_service = Device(camera, client, device_config, auto_config)
                await device_service.initialize()
                self._device_services[camera.identifier] = device_service
                LOGGER.debug(f"Initialized Device service for {camera.identifier}")
            except Exception as error:  # pylint: disable=broad-exception-caught
                LOGGER.error(
                    f"Failed to initialize Device service for {camera.identifier}"
                    f": {error}"
                )

        async def init_media():
            try:
                media_config = config.get(CONFIG_MEDIA, {})
                media_service = Media(camera, client, media_config, auto_config)
                await media_service.initialize()
                self._media_services[camera.identifier] = media_service
                LOGGER.debug(f"Initialized Media service for {camera.identifier}")
            except Exception as error:  # pylint: disable=broad-exception-caught
                LOGGER.error(
                    f"Failed to initialize Media service for {camera.identifier}"
                    f": {error}"
                )

        async def init_imaging():
            try:
                imaging_config = config.get(CONFIG_IMAGING, {})
                imaging_service = Imaging(
                    camera,
                    client,
                    imaging_config,
                    auto_config,
                    self._media_services.get(camera.identifier),
                )
                await imaging_service.initialize()
                self._imaging_services[camera.identifier] = imaging_service
                LOGGER.debug(f"Initialized Imaging service for {camera.identifier}")
            except Exception as error:  # pylint: disable=broad-exception-caught
                LOGGER.warning(
                    f"Failed to initialize Imaging service for {camera.identifier}"
                    f": {error}"
                )

        async def init_ptz():
            try:
                ptz_config = config.get(CONFIG_PTZ, {})
                ptz_service = PTZ(
                    camera,
                    client,
                    ptz_config,
                    auto_config,
                    self._media_services.get(camera.identifier),
                )
                await ptz_service.initialize()
                self._ptz_services[camera.identifier] = ptz_service
                LOGGER.debug(f"Initialized PTZ service for {camera.identifier}")
            except Exception as error:  # pylint: disable=broad-exception-caught
                LOGGER.error(
                    f"Failed to initialize PTZ service for {camera.identifier}"
                    f": {error}"
                )

        loop.run_until_complete(
            asyncio.gather(init_device(), init_media(), init_imaging(), init_ptz())
        )

    # ONVIF Client accessor -> use this to access the ONVIF client in other components

    def get_onvif_client(self, camera_identifier: str) -> ONVIFClient | None:
        """Get the ONVIF client for a camera."""
        return self._onvif_clients.get(camera_identifier)

    # Service accessors -> use these to access ONVIF services in other components

    def get_device_service(self, camera_identifier: str) -> Device | None:
        """Get the Device service for a camera."""
        return self._device_services.get(camera_identifier)

    def get_media_service(self, camera_identifier: str) -> Media | None:
        """Get the Media service for a camera."""
        return self._media_services.get(camera_identifier)

    def get_imaging_service(self, camera_identifier: str) -> Imaging | None:
        """Get the Imaging service for a camera."""
        return self._imaging_services.get(camera_identifier)

    def get_ptz_service(self, camera_identifier: str) -> PTZ | None:
        """Get the PTZ service for a camera."""
        return self._ptz_services.get(camera_identifier)
