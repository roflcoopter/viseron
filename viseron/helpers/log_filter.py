"""Logging filters used by Viseron."""
import logging
import re


class DuplicateFilter(logging.Filter):
    """Formats identical log entries to overwrite the last."""

    # pylint: disable=attribute-defined-outside-init
    def filter(self, record):
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
        record.msg = re.sub(r":\/\/(.*?)\@", r"://*****:*****@", record.msg)
        return True
