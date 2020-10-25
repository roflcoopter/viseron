class Error(Exception):
    """Base class for other exceptions"""


class FFprobeError(Error):
    """Raised when the input value is too small"""
