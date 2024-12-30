"""Download token dataclass."""
from dataclasses import dataclass


@dataclass
class DownloadToken:
    """Download token dataclass."""

    filename: str
    token: str
    delete_after_download: bool
