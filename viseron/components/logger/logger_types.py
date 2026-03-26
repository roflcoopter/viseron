"""Types for the logger component."""

from __future__ import annotations

from typing import TypedDict


class _LoggerViseronData(TypedDict, total=False):
    logs: dict[str, str]
    cameras: dict[str, str]
    default_level: str


class LoggerViseronData(_LoggerViseronData, total=False):
    """TypedDict for logger Viseron data."""

    previous_config: _LoggerViseronData
