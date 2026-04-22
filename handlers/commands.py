"""
Basic command handlers: /start, /help, /status
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import require_auth
from config import ALLOWED_USERS

logger = logging.getLogger(__name__)

HELP_TEXT = """
🏆 *Sienova Converter Bot* — by GangLeader

*COMMANDS*

📥 *Extract & Convert*
`/extract` — Upload an HTML quiz file → get JSON + HTML(s)
`/fromjson` — Upload / paste JSON → get HTML(s)
`/both` — Upload HTML(s) → get GangLeader + Sienova + JSON
`/pdf` — Upload IBPS PDF(s) → extract & build HTMLs (no Playwright)

📋 *Other*
`/status` — Bot health check
`/cancel` — Cancel current operation
`/help` — Show this message

━━━━━━━━━━━━━━━━━━━━━━━━
*WORKFLOW*

1️⃣ Send `/extract` → upload your quiz HTML
2️⃣ Bot extracts quizData via Playwright
3️⃣ Choose output mode:
   • `gangleader` — GangLeader branded HTML
   • `sienova` — Sienova branded HTML
   • `both` — Get both HTMLs + JSON
   • `json` — Just the extracted JSON

_You can also paste raw JSON with `/fromjson` to skip extraction._
"""


@require_auth
async def start_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Welcome, *{user.first_name}*!\n\n"
        f"I am the *Sienova Converter Bot* — your quiz HTML builder.\n\n"
        f"Send `/help` to see all commands, or use `/extract` to get started.",
        parse_mode="Markdown"
    )


@require_auth
async def help_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


@require_auth
async def status_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    allowed = len(ALLOWED_USERS) if ALLOWED_USERS else "open (no restriction)"
    await update.message.reply_text(
        f"✅ *Bot is running*\n\n"
        f"Authorised users: `{allowed}`\n"
        f"Engine: Playwright + python-telegram-bot",
        parse_mode="Markdown"
    )
