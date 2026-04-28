"""Types for the Telegram component."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from viseron.components.telegram import TelegramEventNotifier
    from viseron.components.telegram.ptz_control import TelegramPTZ


class TelegramViseronData(TypedDict, total=False):
    """TypedDict for Telegram Viseron data."""

    notifier: TelegramEventNotifier
    ptz: TelegramPTZ | None
