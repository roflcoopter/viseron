"""Public image token dataclass."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PublicImageToken:
    """Public image token dataclass."""

    file_path: str
    token: str
    expires_at: datetime
    remaining_downloads: int
