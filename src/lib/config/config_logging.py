from voluptuous import All, Any, Optional, Schema


def upper_case(data: dict) -> dict:
    data["level"] = data["level"].upper()
    return data


SCHEMA = Schema(
    All(
        upper_case,
        {
            Optional("level", default="INFO"): Any(
                "DEBUG", "INFO", "WARNING", "ERROR", "FATAL"
            )
        },
    )
)


class LoggingConfig:
    schema = SCHEMA

    def __init__(self, logging):
        self._level = logging.level

    @property
    def level(self):
        return self._level
