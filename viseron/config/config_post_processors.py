"""Post processor config."""
from voluptuous import ALLOW_EXTRA, Schema

SCHEMA = Schema(
    {},
    extra=ALLOW_EXTRA,
)


class PostProcessorsConfig:
    """Post processors config."""

    schema = SCHEMA

    def __init__(self, post_processors):
        self._post_processors = post_processors

    @property
    def post_processors(self) -> list:
        """Return all post processor configs."""
        return self._post_processors
