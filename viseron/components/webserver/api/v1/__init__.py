"""Viseron API."""

from viseron.components.webserver.api.v1.auth import AuthAPIHandler
from viseron.components.webserver.api.v1.camera import CameraAPIHandler
from viseron.components.webserver.api.v1.cameras import CamerasAPIHandler
from viseron.components.webserver.api.v1.compreface import ComprefaceAPIHandler
from viseron.components.webserver.api.v1.config import ConfigAPIHandler
from viseron.components.webserver.api.v1.events import EventsAPIHandler
from viseron.components.webserver.api.v1.hls import HlsAPIHandler
from viseron.components.webserver.api.v1.onboarding import OnboardingAPIHandler
from viseron.components.webserver.api.v1.recordings import RecordingsAPIHandler

__all__ = (
    "AuthAPIHandler",
    "CameraAPIHandler",
    "CamerasAPIHandler",
    "ComprefaceAPIHandler",
    "ConfigAPIHandler",
    "EventsAPIHandler",
    "HlsAPIHandler",
    "OnboardingAPIHandler",
    "RecordingsAPIHandler",
)
