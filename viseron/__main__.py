""" Start Viseron """
import logging

from viseron import Viseron

LOGGER = logging.getLogger()


def log_settings():
    """Set custom log settings."""
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)-12s] [%(levelname)-8s] - %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    formatter = MyFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(DuplicateFilter())
    LOGGER.addHandler(handler)


class MyFormatter(logging.Formatter):
    """Log formatter."""

    # pylint: disable=protected-access
    base_format = "[%(asctime)s] [%(name)-24s] [%(levelname)-8s] - %(message)s"
    overwrite_fmt = "\x1b[80D\x1b[1A\x1b[K" + base_format

    def __init__(self):
        super().__init__(
            fmt=self.base_format,
            datefmt="%Y-%m-%d %H:%M:%S",
            style="%",
        )
        self.current_count = 0

    def format(self, record):
        # Save the original format configured by the user
        # when the logger formatter was instantiated
        format_orig = self._style._fmt

        # Replace the original format with one customized by logging level
        if "message repeated" in str(record.msg):
            self._style._fmt = self.overwrite_fmt

        # Call the original formatter class to do the grunt work
        result = logging.Formatter.format(self, record)

        # Restore the original format configured by the user
        self._style._fmt = format_orig

        return result


class DuplicateFilter(logging.Filter):
    """Formats identical log entries to overwrite the last."""

    # pylint: disable=attribute-defined-outside-init
    def filter(self, record):
        current_log = (record.name, record.module, record.levelno, record.msg)
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


def main():
    """Start Viseron."""
    log_settings()
    Viseron()


if __name__ == "__main__":
    main()
