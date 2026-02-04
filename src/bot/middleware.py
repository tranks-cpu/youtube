import functools
import logging
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

from src.config import Config

logger = logging.getLogger(__name__)


def admin_only(func: Callable):
    """Decorator to restrict command to admin user only."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id if update.effective_user else None

        if user_id != Config.ADMIN_CHAT_ID:
            logger.warning(
                f"Unauthorized access attempt by user {user_id} "
                f"for command {func.__name__}"
            )
            return

        return await func(update, context)

    return wrapper
