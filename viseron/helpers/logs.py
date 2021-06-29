"""Logging helpers Viseron."""
import logging
import os
import re
import threading

from colorlog import ColoredFormatter

from viseron.config.config_logging import LoggingConfig


class DuplicateFilter(logging.Filter):
    """Formats identical log entries to overwrite the last."""

    # pylint: disable=attribute-defined-outside-init
    def filter(self, record):
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

    def filter(self, record):
        """Filter log record."""
        record.msg = re.sub(r":\/\/(.*?)\@", r"://*****:*****@", record.msg)
        return True


class FFmpegFilter(logging.Filter):
    """Filter out unimportant logs."""

    def __init__(self, errors_to_ignore, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors_to_ignore = errors_to_ignore

    def filter(self, record):
        """Filter log record."""
        if any(error in record.msg for error in self.errors_to_ignore):
            return False
        return True


class ViseronLogFormat(ColoredFormatter):
    """Log formatter."""

    # pylint: disable=protected-access
    base_format = (
        "%(log_color)s[%(asctime)s] [%(levelname)-8s] [%(name)-24s] - %(message)s"
    )
    overwrite_fmt = "\x1b[80D\x1b[1A\x1b[K" + base_format

    def __init__(self, config: LoggingConfig):

        log_colors = {}
        if config.color_log:
            log_colors = {
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red",
            }

        super().__init__(
            fmt=self.base_format,
            datefmt="%Y-%m-%d %H:%M:%S",
            style="%",
            reset=True,
            log_colors=log_colors,
        )
        self.current_count = 0

    def format(self, record):
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

    def __init__(self, logger, output_level):
        """Log stdout without blocking."""
        super().__init__(name=f"{logger.name}.logpipe", daemon=True)
        self._logger = logger
        self._output_level = output_level
        self._read_filedescriptor, self._write_filedescriptor = os.pipe()
        self.pipe_reader = os.fdopen(self._read_filedescriptor)
        self.start()

    def fileno(self):
        """Return the write file descriptor of the pipe."""
        return self._write_filedescriptor

    def run(self):
        """Run the thread, logging everything."""
        for line in iter(self.pipe_reader.readline, ""):
            self._logger.log(self._output_level, line.strip("\n"))

        self.pipe_reader.close()

    def close(self):
        """Close the write end of the pipe."""
        os.close(self._write_filedescriptor)
