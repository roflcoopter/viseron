"""Telegram utilities."""
import logging
from functools import wraps

from telegram import Update
from telegram.ext import CallbackContext

from viseron.components.telegram.const import (
    CONFIG_TELEGRAM_CHAT_IDS,
    CONFIG_TELEGRAM_LOG_IDS,
    CONFIG_TELEGRAM_USER_IDS,
)

LOGGER = logging.getLogger(__name__)


def limit_user_access(func):
    """Limit user access to Telegram bot commands."""

    @wraps(func)
    async def wrapper(self, update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id if update and update.effective_user else None
        chat = update.effective_chat if update else None
        chat_type = getattr(chat, "type", None)
        is_private = chat_type == "private"

        # pylint: disable=protected-access
        allowed_users = self._config.get(CONFIG_TELEGRAM_USER_IDS, []) or []
        allowed_chats = self._config.get(CONFIG_TELEGRAM_CHAT_IDS, []) or []

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
            if self._config.get(CONFIG_TELEGRAM_LOG_IDS, False):
                LOGGER.warning("Access denied for user %s.", user_id or "<unknown>")
            if update.message:
                await update.message.reply_text(
                    text=f"Access denied for user {user_id or '<unknown>'}.",
                )
        return None

    return wrapper
