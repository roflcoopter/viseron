"""Config of the webserver component."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from viseron.helpers.config_model import ComponentRoot, ConfigModel
from viseron.helpers.config_types import NoneToDict

from .const import (
    DEFAULT_DEBUG,
    DEFAULT_PUBLIC_URL_EXPIRY_HOURS,
    DEFAULT_PUBLIC_URL_MAX_DOWNLOADS,
    DEFAULT_RATE_LIMIT_LOGIN_MAX_ATTEMPTS,
    DEFAULT_RATE_LIMIT_ONBOARDING_MAX_ATTEMPTS,
    DEFAULT_RATE_LIMIT_TOKEN_MAX_ATTEMPTS,
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    DESC_AUTH,
    DESC_COMPONENT,
    DESC_DAYS,
    DESC_DEBUG,
    DESC_HOURS,
    DESC_MAX_ATTEMPTS,
    DESC_MINUTES,
    DESC_PORT,
    DESC_PUBLIC_BASE_URL,
    DESC_PUBLIC_URL_EXPIRY_HOURS,
    DESC_PUBLIC_URL_MAX_DOWNLOADS,
    DESC_RATE_LIMIT_LOGIN,
    DESC_RATE_LIMIT_ONBOARDING,
    DESC_RATE_LIMIT_TOKEN,
    DESC_RATE_LIMITS,
    DESC_SESSION_EXPIRY,
    DESC_SUBPATH,
    DESC_WINDOW_SECONDS,
)

MaxAttempts = Annotated[int, Field(ge=1, description=DESC_MAX_ATTEMPTS)]
WindowSeconds = Annotated[float, Field(ge=1, description=DESC_WINDOW_SECONDS)]


class LoginRateLimit(ConfigModel):
    """Rate limit of the login endpoint."""

    max_attempts: MaxAttempts = DEFAULT_RATE_LIMIT_LOGIN_MAX_ATTEMPTS
    window_seconds: WindowSeconds = DEFAULT_RATE_LIMIT_WINDOW_SECONDS


class TokenRateLimit(ConfigModel):
    """Rate limit of the token endpoint."""

    max_attempts: MaxAttempts = DEFAULT_RATE_LIMIT_TOKEN_MAX_ATTEMPTS
    window_seconds: WindowSeconds = DEFAULT_RATE_LIMIT_WINDOW_SECONDS


class OnboardingRateLimit(ConfigModel):
    """Rate limit of the onboarding endpoint."""

    max_attempts: MaxAttempts = DEFAULT_RATE_LIMIT_ONBOARDING_MAX_ATTEMPTS
    window_seconds: WindowSeconds = DEFAULT_RATE_LIMIT_WINDOW_SECONDS


class RateLimits(ConfigModel):
    """Per-IP rate limits of the authentication endpoints."""

    login: Annotated[LoginRateLimit, NoneToDict] = Field(
        default_factory=LoginRateLimit, description=DESC_RATE_LIMIT_LOGIN
    )
    token: Annotated[TokenRateLimit, NoneToDict] = Field(
        default_factory=TokenRateLimit, description=DESC_RATE_LIMIT_TOKEN
    )
    onboarding: Annotated[OnboardingRateLimit, NoneToDict] = Field(
        default_factory=OnboardingRateLimit, description=DESC_RATE_LIMIT_ONBOARDING
    )


class SessionExpiry(ConfigModel):
    """Time after which a session expires."""

    days: int = Field(default=0, ge=0, description=DESC_DAYS)
    hours: int = Field(default=0, ge=0, description=DESC_HOURS)
    minutes: int = Field(default=0, ge=0, description=DESC_MINUTES)


class AuthConfig(ConfigModel):
    """Authentication config."""

    session_expiry: SessionExpiry | None = Field(
        default=None, description=DESC_SESSION_EXPIRY
    )
    rate_limits: Annotated[RateLimits, NoneToDict] = Field(
        default_factory=RateLimits, description=DESC_RATE_LIMITS
    )


class WebserverConfig(ConfigModel):
    """Config of the webserver component."""

    port: int | None = Field(
        default=None, ge=1024, le=49151, description=DESC_PORT, deprecated=True
    )
    debug: bool = Field(default=DEFAULT_DEBUG, description=DESC_DEBUG)
    subpath: str | None = Field(default=None, description=DESC_SUBPATH)
    public_base_url: str | None = Field(default=None, description=DESC_PUBLIC_BASE_URL)
    public_url_expiry_hours: int = Field(
        default=DEFAULT_PUBLIC_URL_EXPIRY_HOURS,
        ge=1,
        le=744,
        description=DESC_PUBLIC_URL_EXPIRY_HOURS,
    )
    public_url_max_downloads: int = Field(
        default=DEFAULT_PUBLIC_URL_MAX_DOWNLOADS,
        ge=0,
        description=DESC_PUBLIC_URL_MAX_DOWNLOADS,
    )
    # None when the key is not set. Setting it, even to null, enables auth.
    auth: Annotated[AuthConfig | None, NoneToDict] = Field(
        default=None, description=DESC_AUTH
    )


class WebserverRoot(ComponentRoot):
    """Config with the webserver component at the root."""

    webserver: Annotated[WebserverConfig, NoneToDict] = Field(
        default_factory=WebserverConfig, description=DESC_COMPONENT
    )
