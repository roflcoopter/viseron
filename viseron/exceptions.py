"""Exceptions used by Viseron."""


class ViseronError(Exception):
    """General Viseron exception occurred."""


class FFprobeError(ViseronError):
    """Raised when FFprobe returns an error."""

    def __init__(self, ffprobe_output: dict) -> None:
        """Initialize error."""
        super().__init__(self)
        self.ffprobe_output = ffprobe_output

    def __str__(self) -> str:
        """Return string representation."""
        return f"FFprobe could not connect to stream: {self.ffprobe_output}"


class StreamInformationError(ViseronError):
    """Raised when FFprobe fails to get stream information."""

    def __init__(self, width, height, fps) -> None:
        """Initialize error."""
        super().__init__(self)
        self.width = width
        self.height = height
        self.fps = fps

    def __str__(self) -> str:
        """Return string representation."""
        return (
            "Could not get needed stream information. "
            "Missing atleast one of width, height or fps. "
            f"Width: {self.width} "
            f"Height: {self.height} "
            f"FPS: {self.fps} "
        )
