"""Telegram utilities."""

import logging
from collections.abc import Callable, Sequence
from functools import wraps
from typing import Any

from telegram import Update
from telegram.ext import CallbackContext

LOGGER = logging.getLogger(__name__)


def parse_command_args(
    args: Sequence[str] | None,
    /,
    **params: tuple[Callable[[str], Any], Any],
) -> list[Any]:
    """Parse the positional arguments of a Telegram command.

    Each keyword argument is a (converter, default) tuple. The keywords name the
    parameters for readability and are matched against the arguments supplied in
    the Telegram message in the order they are given. Arguments that are not
    supplied fall back to their default.
    """
    given = args or []
    return [
        converter(given[index]) if index < len(given) else default
        for index, (converter, default) in enumerate(params.values())
    ]


def limit_user_access(func):
    """Limit user access to Telegram bot commands."""

    @wraps(func)
    async def wrapper(self, update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id if update and update.effective_user else None
        chat = update.effective_chat if update else None
        chat_type = getattr(chat, "type", None)
        is_private = chat_type == "private"

        # pylint: disable=protected-access
        allowed_users = self._config.telegram_user_ids
        allowed_chats = self._config.telegram_chat_ids

        allowed = False
        if user_id is not None:
            if user_id in allowed_users:
                allowed = True
            elif is_private and user_id in allowed_chats:
                # In private chats, chat_id == user_id, allow if configured in chat_ids
                allowed = True

        if allowed:
            return await func(self, update, context, *args, **kwargs)

        if update:
            # pylint: disable=protected-access
            if self._config.telegram_log_ids:
                LOGGER.warning("Access denied for user %s.", user_id or "<unknown>")
            if update.message:
                await update.message.reply_text(
                    text=f"Access denied for user {user_id or '<unknown>'}.",
                )
        return None

    return wrapper
