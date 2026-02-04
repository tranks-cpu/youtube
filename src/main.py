import logging
import sys

from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from src.bot.handlers import (
    cmd_start,
    cmd_add_channel,
    cmd_summarize,
    menu_callback,
    handle_channel_url,
    handle_video_url,
    handle_schedule_time,
    handle_remove_channel,
    cancel,
    WAITING_CHANNEL_URL,
    WAITING_VIDEO_URL,
    WAITING_SCHEDULE_TIME,
    WAITING_REMOVE_CHANNEL,
)
from src.config import Config
from src.db.database import init_db
from src.services.scheduler import setup_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the bot."""
    errors = Config.validate()
    if errors:
        for error in errors:
            logger.error(error)
        sys.exit(1)

    init_db()
    logger.info("Database initialized")

    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Conversation handler for interactive menu
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(menu_callback, pattern="^menu_"),
        ],
        states={
            WAITING_CHANNEL_URL: [
                CallbackQueryHandler(menu_callback, pattern="^(cancel|menu_)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel_url),
            ],
            WAITING_VIDEO_URL: [
                CallbackQueryHandler(menu_callback, pattern="^(cancel|menu_)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_video_url),
            ],
            WAITING_SCHEDULE_TIME: [
                CallbackQueryHandler(menu_callback, pattern="^(cancel|menu_)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_schedule_time),
            ],
            WAITING_REMOVE_CHANNEL: [
                CallbackQueryHandler(handle_remove_channel, pattern="^(remove_|menu_)"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(menu_callback, pattern="^menu_"),
        ],
    )

    application.add_handler(conv_handler)

    # Legacy direct command handlers
    application.add_handler(CommandHandler("add_channel", cmd_add_channel))
    application.add_handler(CommandHandler("summarize", cmd_summarize))

    setup_scheduler(application)

    logger.info("Bot starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
