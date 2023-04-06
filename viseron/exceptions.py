"""Exceptions used by Viseron."""
from __future__ import annotations


class ViseronError(Exception):
    """General Viseron exception occurred."""


class NotReadyError(ViseronError):
    """Base class for component and domain not-ready errors."""

    def __str__(self) -> str:
        """Return error."""
        return super().__str__() or str(self.__cause__)


class ComponentNotReady(NotReadyError):
    """Error that indicates that a component is not ready.

    Note that Viseron will retry the setup of components in the background, thus
    this exception should only be raised in components that DOES NOT call setup_domain.
    If that happens, those domains will never be setup.
    """


class DomainNotReady(NotReadyError):
    """Error that indicates that a domain is not ready.

    It is VERY important that this exception is never raised after
    add_entity/add_entities is called, since that will cause the entity to be added
    twice and cause issues.
    """


class DataStreamNotLoaded(ViseronError):
    """Error that indicates that data stream component is not loaded."""


class FFprobeError(ViseronError):
    """Raised when FFprobe returns an error."""

    def __init__(
        self,
        ffprobe_output: bytes | str | dict,
    ) -> None:
        """Initialize error."""
        super().__init__(self)
        self.ffprobe_output = ffprobe_output

    def __str__(self) -> str:
        """Return string representation."""
        return f"FFprobe could not connect to stream. Output: {self.ffprobe_output!r}"


class FFprobeTimeout(ViseronError):
    """Raised when FFprobe times out."""

    def __init__(self, timeout) -> None:
        """Initialize error."""
        super().__init__(self)
        self.timeout = timeout

    def __str__(self) -> str:
        """Return string representation."""
        return f"FFprobe command timed out after {self.timeout}s"


class StreamInformationError(ViseronError):
    """Raised when FFprobe fails to get stream information."""

    def __init__(
        self, width: int | None, height: int | None, fps: int, codec: str | None
    ) -> None:
        """Initialize error."""
        super().__init__(self)
        self.width = width
        self.height = height
        self.fps = fps
        self.codec = codec

    def __str__(self) -> str:
        """Return string representation."""
        return (
            "Could not get needed stream information. "
            "Missing at least one of width, height, fps or codec. "
            "You can specify the missing information in the config to circumvent this."
            f"Width: {self.width} "
            f"Height: {self.height} "
            f"FPS: {self.fps} "
            f"Codec: {self.codec}"
        )


class DomainNotRegisteredError(ViseronError):
    """Raised when trying to get a domain that has not been registered."""

    def __init__(self, domain: str, identifier: str | None = None) -> None:
        """Initialize error."""
        super().__init__(self)
        self.domain = domain
        self.identifier = identifier

    def __str__(self) -> str:
        """Return string representation."""
        return ("Requested domain{}{}has not been registered").format(
            self.domain,
            f" with identifier {self.identifier} " if self.identifier else " ",
        )


class Unauthorized(ViseronError):
    """Raised when an unauthorized action is attempted."""
