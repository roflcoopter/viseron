"""Logging helpers Viseron."""
from __future__ import annotations

import io
import logging
import os
import re
import threading
import typing
from collections.abc import Callable, Iterable, Iterator
from types import TracebackType
from typing import Any, AnyStr, Literal, TextIO

from colorlog import ColoredFormatter

LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-8s] [%(name)s] - %(message)s"
STREAM_LOG_FORMAT = "%(log_color)s" + LOG_FORMAT
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


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
                    record.msg = "{}, message repeated {} times".format(
                        record.msg, self.current_count + 1
                    )
        except ValueError:
            pass
        return True


class SensitiveInformationFilter(logging.Filter):
    """Redacts sensitive information from logs."""

    sensitive_strings: list[str] = []

    @classmethod
    def add_sensitive_string(cls, sensitive_string: str) -> None:
        """Add a sensitive string to the list of strings to redact."""
        if sensitive_string not in cls.sensitive_strings:
            cls.sensitive_strings.append(sensitive_string)

    @classmethod
    def remove_sensitive_string(cls, sensitive_string: str) -> None:
        """Remove a sensitive string from the list of strings to redact."""
        if sensitive_string in cls.sensitive_strings:
            cls.sensitive_strings.remove(sensitive_string)

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record."""
        if isinstance(record.msg, str):
            record.msg = re.sub(r":\/\/(.*?)\@", r"://*****:*****@", record.msg)
            # Based on this answer: https://stackoverflow.com/a/41307057
            record.msg = re.sub(
                r"(\bpassword\W+)([a-zA-z0-9_!\"#$%&'()*+,-.\/:;<=>?@[\]^_`{|}~]+)",
                r"\1*****",
                record.msg,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            record.msg = re.sub(
                r"(\b(access_token)\W+)(\w+)",
                r"\1*****",
                record.msg,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            for sensitive_string in self.sensitive_strings:
                record.msg = record.msg.replace(sensitive_string, "*****")
        return True


class UnhelpfullLogFilter(logging.Filter):
    """Filter out unimportant logs."""

    def __init__(self, errors_to_ignore: list[Any], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.errors_to_ignore = errors_to_ignore

    def filter(self, record) -> bool:
        """Filter log record."""
        if isinstance(record.msg, str) and (
            record.msg == ""
            or record.msg.isspace()
            or not record.msg.strip()
            or record.msg == "\n"
        ):
            return False
        if any(error in record.msg for error in self.errors_to_ignore):
            return False
        return True


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
        format_orig = self._style._fmt

        # Replace the original format with one customized by logging level
        if "message repeated" in str(record.msg):
            self._style._fmt = self.overwrite_fmt

        # Call the original formatter class to do the grunt work
        result = ColoredFormatter.format(self, record)

        # Restore the original format configured by the user
        self._style._fmt = format_orig

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

    def fileno(self):
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
        os.close(self._write_filedescriptor)


class CTypesLogPipe(threading.Thread):
    """Used to pipe filedescriptor (stdout or stderr) to python logging.

    If the read line starts with ERRORLOG it will be logged at the ERROR level.
    Otherwise its logged at the requested loglevel.
    """

    def __init__(self, logger, loglevel, fd: Literal[1, 2]) -> None:
        super().__init__(name=f"{logger.name}.fd{str(fd)}", daemon=True)
        self._logger = logger
        self._loglevel = loglevel
        self._fd = fd

        self._read_filedescriptor, self._write_filedescriptor = os.pipe()
        self.pipe_reader = os.fdopen(self._read_filedescriptor)
        self._old_fd = os.dup(fd)
        os.dup2(self._write_filedescriptor, fd)
        self.start()

    def fileno(self):
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

    def read(self, num: int = -1) -> AnyStr:
        """Read from the stream."""
        raise io.UnsupportedOperation

    def readable(self) -> bool:
        """Return if the stream is readable."""
        raise io.UnsupportedOperation

    def readline(self, limit: int = -1) -> AnyStr:
        """Read a line from the stream."""
        raise io.UnsupportedOperation

    def readlines(self, hint: int = -1) -> list[AnyStr]:
        """Read lines from the stream."""
        raise io.UnsupportedOperation

    def seek(self, offset: int, whence: int = 0) -> int:
        """Seek in the stream."""
        raise io.UnsupportedOperation

    def seekable(self) -> bool:
        """Return if the stream is seekable."""
        raise io.UnsupportedOperation

    def tell(self) -> int:
        """Return the current position in the stream."""
        raise io.UnsupportedOperation

    def truncate(self, size: int | None = None) -> int:
        """Truncate the stream."""
        raise io.UnsupportedOperation

    def writable(self) -> bool:
        """Return if the stream is writable."""
        raise io.UnsupportedOperation

    def writelines(self, lines: Iterable[AnyStr]) -> None:
        """Write lines to the stream."""
        raise io.UnsupportedOperation

    def __next__(self) -> AnyStr:
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
