"""
Entry-point handlers for /extract, /fromjson, /both
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import require_auth
from handlers.conversation import (
    WAITING_FOR_FILE, WAITING_FOR_JSON, KEY_MODE
)

logger = logging.getLogger(__name__)


@require_auth
async def extract_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data[KEY_MODE] = "extract"
    await update.message.reply_text(
        "📤 *Extract Mode*\n\n"
        "Send me the quiz HTML file and I'll extract the data, then let you choose the output format.",
        parse_mode="Markdown"
    )
    return WAITING_FOR_FILE


@require_auth
async def json_to_html_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data[KEY_MODE] = "fromjson"
    await update.message.reply_text(
        "📋 *JSON → HTML Mode*\n\n"
        "Send me a `.json` file (or paste the JSON text directly) and I'll generate your HTML(s).",
        parse_mode="Markdown"
    )
    return WAITING_FOR_JSON


@require_auth
async def html_to_both_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data[KEY_MODE] = "both"
    await update.message.reply_text(
        "⚡ *Both Mode*\n\n"
        "Send me the quiz HTML and I'll generate *both* GangLeader and Sienova HTMLs + JSON automatically.",
        parse_mode="Markdown"
    )
    return WAITING_FOR_FILE


@require_auth
async def generate_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Placeholder — real logic is in conversation.py generate_handler"""
    pass
