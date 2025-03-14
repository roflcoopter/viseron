"""GStreamer configuration specials."""

# Re-export custom_convert from storage to reuse custom_convert for the script gen_docs
from viseron.components.storage.config import custom_convert

__all__ = ("custom_convert",)
