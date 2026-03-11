"""Logging helpers Viseron."""

from __future__ import annotations

import io
import logging
import os
import re
import threading
import typing
from typing import Any, AnyStr, ClassVar, Literal, NoReturn, TextIO

from colorlog import ColoredFormatter

from viseron.const import ENV_DEV_WARNINGS

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from types import TracebackType

LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-8s] [%(name)s] - %(message)s"
STREAM_LOG_FORMAT = "%(log_color)s" + LOG_FORMAT
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

RE_FILTER_URL_CREDENTIALS = re.compile(r":\/\/(.*?)\@")
# Based on this answer: https://stackoverflow.com/a/41307057
RE_FILTER_PASSWORD = re.compile(
    r"(\bpassword\W+)([a-zA-Z0-9_!\"#$%&'()*+,-.\/:;<=>?@[\]^_`{|}~]+)",
    flags=re.IGNORECASE | re.MULTILINE,
)
RE_FILTER_ACCESS_TOKEN = re.compile(
    r"(\b(access_token)\W+)(\w+)",
    flags=re.IGNORECASE | re.MULTILINE,
)


class DuplicateFilter(logging.Filter):
    """Formats identical log entries to overwrite the last."""

    # pylint: disable=attribute-defined-outside-init
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record."""
        current_log = (
            record.name,
            record.module,
            record.levelno,
            record.msg,
            record.args,
        )
        try:
            if current_log != getattr(self, "last_log", None):
                self.last_log = current_log
                self.current_count = 0
            else:
                self.current_count += 1
                if self.current_count > 0:
                    record.msg = (
                        f"{record.msg}, message repeated {self.current_count + 1} times"
                    )
        except (ValueError, TypeError):
            pass
        return True


class SensitiveInformationFilter(logging.Filter):
    """Redacts sensitive information from logs."""

    sensitive_strings: ClassVar[set[str]] = set()

    @classmethod
    def add_sensitive_string(cls, sensitive_string: str) -> bool:
        """Add a sensitive string to the list of strings to redact."""
        if sensitive_string and sensitive_string not in cls.sensitive_strings:
            cls.sensitive_strings.add(sensitive_string)
            return True
        return False

    @classmethod
    def remove_sensitive_string(cls, sensitive_string: str) -> bool:
        """Remove a sensitive string from the list of strings to redact."""
        if sensitive_string in cls.sensitive_strings:
            cls.sensitive_strings.discard(sensitive_string)
            return True
        return False

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record."""
        # Use getMessage() to resolve lazy-formatted logs (e.g. %s args)
        # before applying redaction, then clear args to prevent
        # double-formatting.
        msg = record.getMessage()

        if isinstance(msg, str):
            msg = RE_FILTER_URL_CREDENTIALS.sub(r"://*****:*****@", msg)
            msg = RE_FILTER_PASSWORD.sub(r"\1*****", msg)
            msg = RE_FILTER_ACCESS_TOKEN.sub(r"\1*****", msg)
            for sensitive_string in self.sensitive_strings:
                msg = msg.replace(sensitive_string, "*****")
            record.msg = msg
            record.args = None
        return True


class SensitiveInformationFilterTracker:
    """Keeps track of sensitive information strings.

    Provide helpers to add strings and clear them when needed.
    """

    def __init__(self) -> None:
        self._sensitive_strings: set[str] = set()

    def add_sensitive_string(self, sensitive_string: str) -> None:
        """Add a sensitive string to the list of strings to redact."""
        SensitiveInformationFilter.add_sensitive_string(sensitive_string)
        self._sensitive_strings.add(sensitive_string)

    def remove_sensitive_string(self, sensitive_string: str) -> None:
        """Remove a sensitive string from the list of strings to redact."""
        SensitiveInformationFilter.remove_sensitive_string(sensitive_string)
        self._sensitive_strings.discard(sensitive_string)

    def clear_sensitive_strings(self) -> None:
        """Clear all sensitive strings from the filter."""
        for sensitive_string in self._sensitive_strings:
            SensitiveInformationFilter.remove_sensitive_string(sensitive_string)
        self._sensitive_strings.clear()


class UnhelpfullLogFilter(logging.Filter):
    """Filter out unimportant logs."""

    def __init__(self, errors_to_ignore: list[Any], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.errors_to_ignore = errors_to_ignore

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record."""
        if isinstance(record.msg, str) and (
            record.msg == ""
            or record.msg.isspace()
            or not record.msg.strip()
            or record.msg == "\n"
        ):
            return False
        return not any(error in record.msg for error in self.errors_to_ignore)


class ViseronLogFormat(ColoredFormatter):
    """Log formatter.

    Used only by the StreamHandler logs.
    """

    # pylint: disable=protected-access
    overwrite_fmt = "\x1b[80D\x1b[1A\x1b[K" + STREAM_LOG_FORMAT

    def __init__(self) -> None:
        log_colors = {
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red",
        }

        super().__init__(
            fmt=STREAM_LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT,
            style="%",
            reset=True,
            log_colors=log_colors,
        )
        self.current_count = 0

    def format(self, record: logging.LogRecord) -> str:
        """Format log record."""
        # Save the original format configured by the user
        # when the logger formatter was instantiated
        format_orig = self._style._fmt  # noqa: SLF001

        # Replace the original format with one customized by logging level
        if "message repeated" in str(record.msg):
            self._style._fmt = self.overwrite_fmt  # noqa: SLF001

        # Call the original formatter class to do the grunt work
        result = ColoredFormatter.format(self, record)

        # Restore the original format configured by the user
        self._style._fmt = format_orig  # noqa: SLF001

        return result


class LogPipe(threading.Thread):
    """Used to pipe stderr to python logging."""

    def __init__(
        self,
        logger: logging.Logger,
        output_level: int | None = logging.ERROR,
        output_level_func: Callable[[str], tuple[int, str]] | None = None,
    ) -> None:
        """Log stdout without blocking."""
        super().__init__(name=f"{logger.name}.logpipe", daemon=True)
        self._logger = logger
        self._output_level = output_level
        self._output_level_func = output_level_func
        self._read_filedescriptor, self._write_filedescriptor = os.pipe()
        self.pipe_reader = os.fdopen(self._read_filedescriptor)
        self._kill_received = False
        self.start()

    def fileno(self) -> int:
        """Return the write file descriptor of the pipe."""
        return self._write_filedescriptor

    def run(self) -> None:
        """Run the thread, logging everything."""
        while not self._kill_received:
            line = self.pipe_reader.readline()
            log_str = line.strip().strip("\n")
            if not log_str:
                continue

            output_level: int | None
            if self._output_level_func:
                output_level, log_str = self._output_level_func(log_str)
            else:
                output_level = self._output_level

            # Check if the log level is set to DEBUG, INFO etc
            if output_level in [
                logging.DEBUG,
                logging.INFO,
                logging.WARNING,
                logging.ERROR,
                logging.CRITICAL,
            ]:
                self._logger.log(output_level, log_str)
            else:
                self._logger.log(logging.ERROR, log_str)

        self._logger.debug("LogPipe thread ended")
        self.pipe_reader.close()

    def close(self) -> None:
        """Close the write end of the pipe."""
        self._logger.debug("Closing LogPipe")
        self._kill_received = True
        try:
            os.close(self._write_filedescriptor)
        except OSError:
            pass


class CTypesLogPipe(threading.Thread):
    """Used to pipe filedescriptor (stdout or stderr) to python logging.

    If the read line starts with ERRORLOG it will be logged at the ERROR level.
    Otherwise its logged at the requested loglevel.
    """

    def __init__(
        self, logger: logging.Logger, loglevel: int, fd: Literal[1, 2]
    ) -> None:
        super().__init__(name=f"{logger.name}.fd{fd!s}", daemon=True)
        self._logger = logger
        self._loglevel = loglevel
        self._fd = fd

        self._read_filedescriptor, self._write_filedescriptor = os.pipe()
        self.pipe_reader = os.fdopen(self._read_filedescriptor)
        self._old_fd = os.dup(fd)
        os.dup2(self._write_filedescriptor, fd)
        self.start()

    def fileno(self) -> int:
        """Return the write file descriptor of the pipe."""
        return self._write_filedescriptor

    def run(self) -> None:
        """Run the thread, logging everything."""
        for line in iter(self.pipe_reader.readline, ""):
            if line.startswith("ERRORLOG"):
                self._logger.log(
                    logging.ERROR, line.split("ERRORLOG")[1].strip().strip("\n")
                )
            else:
                self._logger.log(self._loglevel, line.strip().strip("\n"))

        self.pipe_reader.close()

    def close(self) -> None:
        """Close the write end of the pipe."""
        os.close(self._write_filedescriptor)
        os.dup2(self._old_fd, self._fd)


class StreamToLogger(typing.TextIO):
    """Stream object that redirects its output to standard logging."""

    def __init__(self, logger: logging.Logger, log_level: int) -> None:
        """Initialize the object."""
        self.logger = logger
        self.log_level = log_level

    def __enter__(self) -> TextIO:
        """Enter context manager."""
        raise io.UnsupportedOperation

    def close(self) -> None:
        """Close the stream."""
        raise io.UnsupportedOperation

    def fileno(self) -> int:
        """Return the file descriptor."""
        raise io.UnsupportedOperation

    def flush(self) -> None:
        """Flush the stream."""
        raise io.UnsupportedOperation

    def isatty(self) -> bool:
        """Return if the stream is a tty."""
        raise io.UnsupportedOperation

    def read(self, num: int = -1) -> NoReturn:  # noqa: ARG002
        """Read from the stream."""
        raise io.UnsupportedOperation

    def readable(self) -> bool:
        """Return if the stream is readable."""
        raise io.UnsupportedOperation

    def readline(self, limit: int = -1) -> NoReturn:  # noqa: ARG002
        """Read a line from the stream."""
        raise io.UnsupportedOperation

    def readlines(self, hint: int = -1) -> list[AnyStr]:  # noqa: ARG002
        """Read lines from the stream."""
        raise io.UnsupportedOperation

    def seek(self, offset: int, whence: int = 0) -> int:  # noqa: ARG002
        """Seek in the stream."""
        raise io.UnsupportedOperation

    def seekable(self) -> bool:
        """Return if the stream is seekable."""
        raise io.UnsupportedOperation

    def tell(self) -> int:
        """Return the current position in the stream."""
        raise io.UnsupportedOperation

    def truncate(self, size: int | None = None) -> int:  # noqa: ARG002
        """Truncate the stream."""
        raise io.UnsupportedOperation

    def writable(self) -> bool:
        """Return if the stream is writable."""
        raise io.UnsupportedOperation

    def writelines(self, lines: Iterable[AnyStr]) -> None:  # noqa: ARG002
        """Write lines to the stream."""
        raise io.UnsupportedOperation

    def __next__(self) -> NoReturn:
        """Return the next line from the stream."""
        raise io.UnsupportedOperation

    def __iter__(self) -> Iterator[AnyStr]:
        """Return an iterator over the stream."""
        raise io.UnsupportedOperation

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit context manager."""
        raise io.UnsupportedOperation

    def write(self, text: str) -> int:
        """Write to the logger."""
        if text == "\n":
            return 0
        self.logger.log(self.log_level, text.rstrip())
        return 1


def development_warning(logger: logging.Logger, message: str) -> None:
    """Log a warning in development mode."""
    if os.environ.get(ENV_DEV_WARNINGS, None):
        logger.warning(message)
