"""Exceptions used by Viseron."""
from typing import Union


class ViseronError(Exception):
    """General Viseron exception occurred."""


class FFprobeError(ViseronError):
    """Raised when FFprobe returns an error."""

    def __init__(
        self, ffprobe_output: Union[bytes, str, dict], ffprobe_command: list
    ) -> None:
        """Initialize error."""
        super().__init__(self)
        self.ffprobe_output = ffprobe_output
        self.ffprobe_command = ffprobe_command

    def __str__(self) -> str:
        """Return string representation."""
        return (
            "FFprobe could not connect to stream. "
            f"Output: {self.ffprobe_output}, "
            f"Command: {' '.join(self.ffprobe_command)}"
        )


class FFprobeTimeout(ViseronError):
    """Raised when FFprobe times out."""

    def __init__(self, ffprobe_command, timeout) -> None:
        """Initialize error."""
        super().__init__(self)
        self.ffprobe_command = ffprobe_command
        self.timeout = timeout

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"FFprobe command {' '.join(self.ffprobe_command)} "
            f"timed out after {self.timeout}s"
        )


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
            "Missing at least one of width, height or fps. "
            f"Width: {self.width} "
            f"Height: {self.height} "
            f"FPS: {self.fps} "
        )


class DuplicateDecoderName(ViseronError):
    """Raised when a decoder is instantiated with a duplicate name."""

    def __init__(self, decoder_name: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.decoder_name = decoder_name

    def __str__(self) -> str:
        """Return string representation."""
        return f"A decoder with name {self.decoder_name} already exist"


class DetectorModuleNotFoundError(ViseronError):
    """Raised when an object detector does not exist."""

    def __init__(self, detector: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.detector = detector

    def __str__(self) -> str:
        """Return string representation."""
        return f"Object detector {self.detector} not found"


class DetectorImportError(ViseronError):
    """Raised when a detector cannot be imported properly."""

    def __init__(self, detector: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.detector = detector

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"Could not import {self.detector}. A class named "
            "ObjectDetection which inherits from AbstractObjectDetection is required"
        )


class DetectorConfigError(ViseronError):
    """Raised when a detectors config cannot be imported properly."""

    def __init__(self, detector: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.detector = detector

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"Could not import {self.detector}. A class named "
            "Config which inherits from AbstractDetectorConfig is required"
        )


class DetectorConfigSchemaError(ViseronError):
    """Raised when a detectors schema cannot be found."""

    def __init__(self, detector: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.detector = detector

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"Could not import {self.detector}.config. A constant named "
            "SCHEMA which extends from AbstractDetectorConfig.schema is required"
        )


class PostProcessorImportError(ViseronError):
    """Raised when a post processor cannot be imported properly."""

    def __init__(self, processor: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.processor = processor

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"Could not import post processor {self.processor}. Check your config.yaml"
        )


class PostProcessorStructureError(ViseronError):
    """Raised when a post processors structure is wrong."""

    def __init__(self, processor: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.processor = processor

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"Could not import post processor {self.processor}. A class named "
            "Processor which inherits from AbstractProcessor is required"
        )


class MotionModuleNotFoundError(ViseronError):
    """Raised when a motion detector does not exist."""

    def __init__(self, detector: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.detector = detector

    def __str__(self) -> str:
        """Return string representation."""
        return f"Motion detector {self.detector} not found"


class MotionImportError(ViseronError):
    """Raised when a motion detector cannot be imported properly."""

    def __init__(self, detector: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.detector = detector

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"Could not import {self.detector}. A class named "
            "MotionDetection which inherits from AbstractMotionDetection is required"
        )


class MotionConfigError(ViseronError):
    """Raised when a motion detectors config cannot be imported properly."""

    def __init__(self, detector: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.detector = detector

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"Could not import {self.detector}. A class named "
            "Config which inherits from AbstractMotionDetectionConfig is required"
        )


class MotionConfigSchemaError(ViseronError):
    """Raised when a motion detectors schema cannot be found."""

    def __init__(self, detector: str) -> None:
        """Initialize error."""
        super().__init__(self)
        self.detector = detector

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"Could not import {self.detector}.config. A constant named "
            "SCHEMA which extends from AbstractMotionDetectionConfig.schema is required"
        )
