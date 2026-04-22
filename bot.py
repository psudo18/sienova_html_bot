#!/usr/bin/env python3
"""Sienova Converter Bot — entry point"""

import logging
import os
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from handlers.auth import require_auth
from handlers.commands import start_handler, help_handler, status_handler
from handlers.generate import extract_handler, json_to_html_handler, html_to_both_handler
from handlers.conversation import (
    WAITING_FOR_FILE, WAITING_FOR_JSON, WAITING_FOR_MODE, BATCH_COLLECTING,
    file_received_handler, json_received_handler,
    batch_collect_handler, generate_handler, cancel_handler
)
from config import BOT_TOKEN, LOG_LEVEL

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO)
)
logger = logging.getLogger(__name__)


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set. Exiting.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("extract", extract_handler),
            CommandHandler("fromjson", json_to_html_handler),
            CommandHandler("both",    html_to_both_handler),
        ],
        states={
            # New batch collection state — receives multiple HTML files
            BATCH_COLLECTING: [
                MessageHandler(filters.Document.ALL, batch_collect_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, batch_collect_handler),
            ],
            # Legacy single-file state (kept for /both single-file path)
            WAITING_FOR_FILE: [
                MessageHandler(filters.Document.ALL, file_received_handler),
            ],
            WAITING_FOR_JSON: [
                MessageHandler(filters.Document.ALL, json_received_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, json_received_handler),
            ],
            WAITING_FOR_MODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, generate_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start",  start_handler))
    app.add_handler(CommandHandler("help",   help_handler))
    app.add_handler(CommandHandler("status", status_handler))

    logger.info("Sienova Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
