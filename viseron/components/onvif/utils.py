"""Utility functions for ONVIF component."""

from __future__ import annotations

import functools
import json
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import zeep.helpers
from onvif import ONVIFOperationException

from viseron.components.go2rtc.const import COMPONENT as GO2RTC_COMPONENT

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


def to_dict(zeep_object: Any) -> dict[str, Any] | list[dict[str, Any]]:
    """Convert zeep object(s) to JSON-serializable dictionary."""
    if zeep_object is None:
        return {}

    # Serialize using zeep's helper
    if isinstance(zeep_object, list):
        serialized = [zeep.helpers.serialize_object(obj) for obj in zeep_object]
    else:
        serialized = zeep.helpers.serialize_object(zeep_object)

    # Convert to JSON and back to ensure full serialization
    # This handles any remaining XML elements or non-serializable types
    try:
        return json.loads(json.dumps(serialized, default=str))
    except (TypeError, ValueError) as error:
        LOGGER.warning(
            f"Error serializing zeep object, using string conversion: {error}"
        )
        return json.loads(json.dumps(serialized, default=str))


def operation():
    """Handle any ONVIF operations."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except (
                ONVIFOperationException,  # must exists !
                TypeError,
                ValueError,
                RuntimeError,
            ) as error:
                # pylint: disable=protected-access
                LOGGER.error(
                    f"ONVIF error in '{func.__name__}' for camera "
                    f"{self._camera.identifier}: {error}"
                )
                return False

        return wrapper

    return decorator


async def find_matching_profile_token(
    camera: AbstractCamera,
    media_service,
    profiles,
) -> Any:
    """Find the profile that matches the camera's RTSP URL."""
    camera_rtsp_url = extract_rtsp_from_go2rtc(camera)  # prioritize go2rtc config

    if camera_rtsp_url is None:
        camera_rtsp_url = build_camera_rtsp_url(camera)

    if not camera_rtsp_url:
        return None

    for profile in profiles:
        try:
            stream_uri_result = await media_service.get_stream_uri(
                profile_token=profile.token,
            )

            if stream_uri_result is False:
                continue

            if hasattr(stream_uri_result, "Uri"):
                profile_rtsp_url = stream_uri_result.Uri

                # Compare URLs (case insensitive, ignoring credentials)
                if urls_match(camera_rtsp_url, profile_rtsp_url):
                    LOGGER.debug(
                        f"Found matching profile {profile.token} for camera "
                        f"{camera.identifier}"
                    )
                    return profile

        except (AttributeError, TypeError, ValueError, RuntimeError) as error:
            LOGGER.warning(f"Error processing profile {profile.token}: {error}")
            continue

    return None


def extract_rtsp_from_go2rtc(camera: AbstractCamera) -> str | None:
    """Extract RTSP URL from go2rtc configuration."""
    try:
        vis = camera._vis  # pylint: disable=protected-access

        if GO2RTC_COMPONENT not in vis.data:
            return None

        go2rtc_component = vis.data[GO2RTC_COMPONENT]
        # pylint: disable=protected-access
        if not hasattr(go2rtc_component, "_config"):
            return None

        if GO2RTC_COMPONENT not in go2rtc_component._config:
            return None

        go2rtc_config = go2rtc_component._config[GO2RTC_COMPONENT]

        if "streams" not in go2rtc_config:
            return None
        streams = go2rtc_config["streams"]

        camera_id = camera.identifier
        if camera_id not in streams:
            return None

        stream_sources = streams[camera_id]

        if isinstance(stream_sources, list) and len(stream_sources) > 0:
            for idx, source in enumerate(stream_sources):
                if isinstance(source, str) and source.startswith("rtsp://"):
                    LOGGER.debug(
                        f"Found RTSP URL in go2rtc for {camera_id} at index {idx}"
                    )
                    return source

        if isinstance(stream_sources, str) and stream_sources.startswith("rtsp://"):
            return stream_sources
        return None

    except (AttributeError, KeyError, TypeError, ValueError) as error:
        LOGGER.warning(
            f"Error extracting RTSP URL from go2rtc config for camera "
            f"{camera.identifier}: {error}"
        )
        return None


def build_camera_rtsp_url(
    camera: AbstractCamera,
) -> str | None:
    """Build RTSP URL from camera configuration."""
    try:
        if not hasattr(camera, "config"):
            return None

        config = camera.config

        host = config.get("host")
        if not host:
            return None
        path = config.get("path", "")
        port = config.get("port")
        protocol = config.get("protocol") or "rtsp"

        # Build URL
        if port and port != 554:
            url = f"{protocol}://{host}:{port}{path}"
        else:
            url = f"{protocol}://{host}{path}"

        return url

    except (AttributeError, KeyError, TypeError, ValueError) as error:
        LOGGER.debug(f"Error building camera RTSP URL: {error}")
        return None


def urls_match(url1: str, url2: str) -> bool:
    """Compare two RTSP URLs, ignoring credentials and minor differences."""
    try:
        parsed1 = urlparse(url1.lower())
        parsed2 = urlparse(url2.lower())

        if parsed1.scheme != parsed2.scheme:
            return False

        if parsed1.hostname != parsed2.hostname:
            return False

        port1 = parsed1.port or (554 if parsed1.scheme == "rtsp" else 80)
        port2 = parsed2.port or (554 if parsed2.scheme == "rtsp" else 80)
        if port1 != port2:
            return False

        if parsed1.path.rstrip("/") != parsed2.path.rstrip("/"):
            return False

        return True

    except (AttributeError, KeyError, TypeError, ValueError) as error:
        LOGGER.debug(f"Error comparing URLs: {error}")
        return False
