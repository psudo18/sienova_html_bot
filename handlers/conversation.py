"""
Conversation flow states and shared handlers
"""

import os
import json
import logging
import tempfile
from pathlib import Path
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from handlers.auth import require_auth
from utils.extractor import extract_quiz_from_html
from utils.builder import build_html
from config import TEMP_DIR

logger = logging.getLogger(__name__)

# ── States ────────────────────────────────────────────────────────────────────
WAITING_FOR_FILE  = 1
WAITING_FOR_JSON  = 2
WAITING_FOR_MODE  = 3

# Keys stored in user_data
KEY_MODE      = "flow_mode"   # "extract" | "fromjson" | "both"
KEY_QUIZ_DATA = "quiz_data"
KEY_TEST_NAME = "test_name"

MODE_KEYBOARD = ReplyKeyboardMarkup(
    [["gangleader", "sienova"], ["both", "json"]],
    one_time_keyboard=True,
    resize_keyboard=True,
)

os.makedirs(TEMP_DIR, exist_ok=True)


# ── cancel ────────────────────────────────────────────────────────────────────
@require_auth
async def cancel_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text(
        "❌ Operation cancelled.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# ── file received (HTML upload during /extract or /both) ─────────────────────
@require_auth
async def file_received_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        await update.message.reply_text("Please send an HTML file.")
        return WAITING_FOR_FILE

    if not doc.file_name.lower().endswith(".html"):
        await update.message.reply_text("⚠️ Only `.html` files are accepted here.")
        return WAITING_FOR_FILE

    status = await update.message.reply_text("⏳ Downloading file...")

    # Download the file
    tmp_path = os.path.join(TEMP_DIR, f"{update.effective_user.id}_{doc.file_name}")
    tg_file = await ctx.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(tmp_path)

    await update.message.reply_text("🔍 Extracting quiz data via Playwright... (may take 10–20s)")

    # Extract quiz data via Playwright
    quiz_data = await extract_quiz_from_html(tmp_path)

    if not quiz_data:
        await update.message.reply_text(
            "❌ Could not extract `quizData` from this HTML.\n\n"
            "Make sure the file has a `quizData` JavaScript variable.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # Store in user_data
    test_name = doc.file_name.replace(".html", "").replace("_", " ")
    ctx.user_data[KEY_QUIZ_DATA] = quiz_data
    ctx.user_data[KEY_TEST_NAME] = test_name

    flow = ctx.user_data.get(KEY_MODE, "extract")

    if flow == "both":
        await update.message.reply_text(
            f"✅ Extracted *{len(quiz_data['questions'])}* questions from `{doc.file_name}`\n"
            f"⚙️ Generating both HTMLs now...",
            parse_mode="Markdown"
        )
        await _send_outputs(update, ctx, "both")
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            f"✅ Extracted *{len(quiz_data['questions'])}* questions from `{doc.file_name}`\n\n"
            f"Choose output format:",
            parse_mode="Markdown",
            reply_markup=MODE_KEYBOARD
        )
        return WAITING_FOR_MODE


# ── JSON received (/fromjson) ─────────────────────────────────────────────────
@require_auth
async def json_received_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw_json = None

    if update.message.document:
        doc = update.message.document
        if not doc.file_name.lower().endswith(".json"):
            await update.message.reply_text("⚠️ Please send a `.json` file or paste JSON text.")
            return WAITING_FOR_JSON
        tmp_path = os.path.join(TEMP_DIR, f"{update.effective_user.id}_{doc.file_name}")
        tg_file = await ctx.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            raw_json = f.read()
    elif update.message.text:
        raw_json = update.message.text.strip()

    if not raw_json:
        await update.message.reply_text("❓ Send a JSON file or paste JSON text.")
        return WAITING_FOR_JSON

    try:
        quiz_data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        await update.message.reply_text(f"❌ Invalid JSON: {e}")
        return WAITING_FOR_JSON

    # Normalise: accept both raw list and formatted dict
    if isinstance(quiz_data, list):
        from utils.extractor import format_data
        quiz_data = format_data(quiz_data, "Imported Test")

    ctx.user_data[KEY_QUIZ_DATA] = quiz_data
    ctx.user_data[KEY_TEST_NAME] = quiz_data.get("test_name", "Imported Test")

    q_count = len(quiz_data.get("questions", []))
    await update.message.reply_text(
        f"✅ Loaded *{q_count}* questions.\n\nChoose output format:",
        parse_mode="Markdown",
        reply_markup=MODE_KEYBOARD
    )
    return WAITING_FOR_MODE


# ── Mode selected → generate ──────────────────────────────────────────────────
@require_auth
async def generate_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mode = update.message.text.strip().lower()
    valid = {"gangleader", "sienova", "both", "json"}
    if mode not in valid:
        await update.message.reply_text(
            "Please choose: `gangleader`, `sienova`, `both`, or `json`",
            parse_mode="Markdown",
            reply_markup=MODE_KEYBOARD
        )
        return WAITING_FOR_MODE

    await update.message.reply_text(
        f"⚙️ Generating `{mode}` output...",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    await _send_outputs(update, ctx, mode)
    return ConversationHandler.END


# ── Internal: build & send files ──────────────────────────────────────────────
async def _send_outputs(update, ctx, mode):
    quiz_data = ctx.user_data.get(KEY_QUIZ_DATA)
    test_name = ctx.user_data.get(KEY_TEST_NAME, "quiz")
    safe_name = test_name.replace(" ", "_").lower()
    uid = update.effective_user.id

    if not quiz_data:
        await update.message.reply_text("❌ No quiz data found. Please start over.")
        return

    try:
        if mode in ("gangleader", "both"):
            gl_html = build_html(quiz_data, brand="gangleader")
            gl_path = os.path.join(TEMP_DIR, f"{uid}_{safe_name}_gangleader.html")
            with open(gl_path, "w", encoding="utf-8") as f:
                f.write(gl_html)
            await update.message.reply_document(
                document=open(gl_path, "rb"),
                filename=f"{safe_name}_gangleader.html",
                caption="🏆 *GangLeader* HTML — ready to use!",
                parse_mode="Markdown"
            )

        if mode in ("sienova", "both"):
            sv_html = build_html(quiz_data, brand="sienova")
            sv_path = os.path.join(TEMP_DIR, f"{uid}_{safe_name}_sienova.html")
            with open(sv_path, "w", encoding="utf-8") as f:
                f.write(sv_html)
            await update.message.reply_document(
                document=open(sv_path, "rb"),
                filename=f"{safe_name}_sienova.html",
                caption="📘 *Sienova* HTML — ready to use!",
                parse_mode="Markdown"
            )

        if mode in ("json", "both"):
            import json as _json
            json_path = os.path.join(TEMP_DIR, f"{uid}_{safe_name}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                _json.dump(quiz_data, f, ensure_ascii=False, indent=2)
            await update.message.reply_document(
                document=open(json_path, "rb"),
                filename=f"{safe_name}.json",
                caption="📄 Extracted *JSON* data",
                parse_mode="Markdown"
            )

        await update.message.reply_text(
            f"✅ Done! `{mode}` output generated for *{test_name}*.",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.exception("Error generating output")
        await update.message.reply_text(f"❌ Error during generation: {e}")

    finally:
        ctx.user_data.clear()
