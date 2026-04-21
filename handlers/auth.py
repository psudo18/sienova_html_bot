"""
Auth middleware - only ALLOWED_USERS can use the bot
"""

import functools
import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED_USERS

logger = logging.getLogger(__name__)


def require_auth(func):
    """Decorator: reject users not in ALLOWED_USERS list."""
    @functools.wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        if ALLOWED_USERS and user.id not in ALLOWED_USERS:
            logger.warning("Blocked unauthorized user %s (%s)", user.id, user.username)
            await update.message.reply_text(
                "⛔ *Access Denied*\n\n"
                "You are not authorised to use this bot.\n"
                "Contact the GangLeader admin to get access.",
                parse_mode="Markdown"
            )
            return

        return await func(update, ctx, *args, **kwargs)
    return wrapper
