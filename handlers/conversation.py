"""
Conversation flow — supports:
- Single file mode: /extract, /fromjson, /both
- Batch mode: drop multiple HTML/JSON files, bot processes them one by one automatically
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
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
BATCH_COLLECTING  = 4   # collecting multiple files

# Keys stored in user_data
KEY_MODE      = "flow_mode"
KEY_QUIZ_DATA = "quiz_data"
KEY_TEST_NAME = "test_name"
KEY_BATCH     = "batch_files"   # list of (file_path, file_name)
KEY_BATCH_IDX = "batch_idx"
KEY_BATCH_MODE= "batch_out_mode"

MODE_KEYBOARD = ReplyKeyboardMarkup(
    [["gangleader", "sienova"], ["both", "json"]],
    one_time_keyboard=True, resize_keyboard=True,
)

os.makedirs(TEMP_DIR, exist_ok=True)


# ── cancel ────────────────────────────────────────────────────────────────────
@require_auth
async def cancel_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── /extract entry ────────────────────────────────────────────────────────────
@require_auth
async def extract_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data[KEY_MODE] = "extract"
    ctx.user_data[KEY_BATCH] = []
    await update.message.reply_text(
        "📤 *Extract Mode*\n\n"
        "Send me one or more quiz HTML files.\n"
        "When you're done sending files, type *done* to start processing.",
        parse_mode="Markdown"
    )
    return BATCH_COLLECTING


# ── /fromjson entry ───────────────────────────────────────────────────────────
@require_auth
async def json_to_html_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data[KEY_MODE] = "fromjson"
    await update.message.reply_text(
        "📋 *JSON → HTML Mode*\n\n"
        "Send me a `.json` file or paste JSON text.\n"
        "I'll generate your HTML(s).",
        parse_mode="Markdown"
    )
    return WAITING_FOR_JSON


# ── /both entry ───────────────────────────────────────────────────────────────
@require_auth
async def html_to_both_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data[KEY_MODE] = "both"
    ctx.user_data[KEY_BATCH] = []
    await update.message.reply_text(
        "⚡ *Both Mode*\n\n"
        "Send me one or more quiz HTML files.\n"
        "Type *done* when finished — I'll generate GangLeader + Sienova + JSON for each.",
        parse_mode="Markdown"
    )
    return BATCH_COLLECTING


# ── BATCH: collecting files ───────────────────────────────────────────────────
@require_auth
async def batch_collect_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Receives HTML files one by one. When user sends 'done', starts processing."""

    # Text message = "done" signal
    if update.message.text:
        text = update.message.text.strip().lower()
        if text in ("done", "start", "go", "process"):
            return await _start_batch(update, ctx)
        else:
            await update.message.reply_text(
                "Send HTML file(s), then type *done* to process them all.",
                parse_mode="Markdown"
            )
            return BATCH_COLLECTING

    # Document received
    doc = update.message.document
    if not doc:
        return BATCH_COLLECTING

    if not doc.file_name.lower().endswith(".html"):
        await update.message.reply_text(f"⚠️ `{doc.file_name}` is not an HTML file — skipped.", parse_mode="Markdown")
        return BATCH_COLLECTING

    # Download it
    tmp_path = os.path.join(TEMP_DIR, f"{update.effective_user.id}_{doc.file_name}")
    tg_file = await ctx.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(tmp_path)

    batch = ctx.user_data.setdefault(KEY_BATCH, [])
    batch.append((tmp_path, doc.file_name))

    await update.message.reply_text(
        f"✅ `{doc.file_name}` queued ({len(batch)} file{'s' if len(batch)>1 else ''} so far)\n"
        f"Send more files or type *done* to process.",
        parse_mode="Markdown"
    )
    return BATCH_COLLECTING


async def _start_batch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    batch = ctx.user_data.get(KEY_BATCH, [])
    if not batch:
        await update.message.reply_text("❌ No files queued. Send HTML files first.")
        return BATCH_COLLECTING

    flow = ctx.user_data.get(KEY_MODE, "extract")

    if flow == "both":
        # Process all immediately with both outputs
        await update.message.reply_text(
            f"⚙️ Processing *{len(batch)}* file(s) → GangLeader + Sienova + JSON...",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        await _process_batch(update, ctx, "both", batch)
        ctx.user_data.clear()
        return ConversationHandler.END
    else:
        # Ask for output mode once, then apply to all files
        await update.message.reply_text(
            f"📋 *{len(batch)}* file(s) queued.\n\nChoose output format for all files:",
            parse_mode="Markdown",
            reply_markup=MODE_KEYBOARD
        )
        return WAITING_FOR_MODE


# ── Mode selected → process batch ─────────────────────────────────────────────
@require_auth
async def generate_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mode = update.message.text.strip().lower()
    valid = {"gangleader", "sienova", "both", "json"}
    if mode not in valid:
        await update.message.reply_text(
            "Please choose: `gangleader`, `sienova`, `both`, or `json`",
            parse_mode="Markdown", reply_markup=MODE_KEYBOARD
        )
        return WAITING_FOR_MODE

    await update.message.reply_text(
        f"⚙️ Generating `{mode}` output...",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )

    flow = ctx.user_data.get(KEY_MODE, "extract")
    batch = ctx.user_data.get(KEY_BATCH, [])

    if batch:
        # Multi-file batch
        await _process_batch(update, ctx, mode, batch)
    else:
        # Single file (quiz_data already in ctx)
        await _send_outputs(update, ctx, mode)

    ctx.user_data.clear()
    return ConversationHandler.END


# ── JSON received ─────────────────────────────────────────────────────────────
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

    if isinstance(quiz_data, list):
        from utils.extractor import format_data
        quiz_data = format_data(quiz_data, "Imported Test")

    ctx.user_data[KEY_QUIZ_DATA] = quiz_data
    ctx.user_data[KEY_TEST_NAME] = quiz_data.get("test_name", "Imported Test")
    ctx.user_data[KEY_BATCH] = []  # no batch for fromjson

    q_count = len(quiz_data.get("questions", []))
    await update.message.reply_text(
        f"✅ Loaded *{q_count}* questions.\n\nChoose output format:",
        parse_mode="Markdown", reply_markup=MODE_KEYBOARD
    )
    return WAITING_FOR_MODE


# ── file received (single /extract flow — kept for backward compat) ────────────
@require_auth
async def file_received_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handles single file in old single-mode flow — redirects to batch."""
    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith(".html"):
        await update.message.reply_text("⚠️ Only `.html` files are accepted.")
        return WAITING_FOR_FILE

    tmp_path = os.path.join(TEMP_DIR, f"{update.effective_user.id}_{doc.file_name}")
    tg_file = await ctx.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(tmp_path)

    await update.message.reply_text("⏳ Downloading...")
    await update.message.reply_text("🔍 Extracting quiz data... (10-20s)")

    quiz_data = await extract_quiz_from_html(tmp_path)
    if not quiz_data:
        await update.message.reply_text(
            "❌ Could not extract `quizData` from this HTML.\n"
            "Make sure the file has a `quizData` JavaScript variable.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    test_name = doc.file_name.replace(".html", "").replace("_", " ")
    ctx.user_data[KEY_QUIZ_DATA] = quiz_data
    ctx.user_data[KEY_TEST_NAME] = test_name
    ctx.user_data[KEY_BATCH] = []

    flow = ctx.user_data.get(KEY_MODE, "extract")
    if flow == "both":
        await update.message.reply_text(
            f"✅ Extracted *{len(quiz_data['questions'])}* questions.\n⚙️ Generating both HTMLs...",
            parse_mode="Markdown"
        )
        await _send_outputs(update, ctx, "both")
        ctx.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ Extracted *{len(quiz_data['questions'])}* questions from `{doc.file_name}`\n\nChoose output format:",
        parse_mode="Markdown", reply_markup=MODE_KEYBOARD
    )
    return WAITING_FOR_MODE


# ── Internal: process a batch of HTML files ───────────────────────────────────
async def _process_batch(update: Update, ctx: ContextTypes.DEFAULT_TYPE, mode: str, batch: list):
    uid  = update.effective_user.id
    total = len(batch)

    for idx, (tmp_path, file_name) in enumerate(batch, 1):
        await update.message.reply_text(
            f"📄 *[{idx}/{total}]* Processing `{file_name}`...",
            parse_mode="Markdown"
        )

        quiz_data = await extract_quiz_from_html(tmp_path)

        if not quiz_data:
            await update.message.reply_text(
                f"❌ *[{idx}/{total}]* Failed to extract from `{file_name}` — skipped.",
                parse_mode="Markdown"
            )
            continue

        test_name = file_name.replace(".html", "").replace("_", " ")
        ctx.user_data[KEY_QUIZ_DATA] = quiz_data
        ctx.user_data[KEY_TEST_NAME] = test_name

        q_count = len(quiz_data.get("questions", []))
        await update.message.reply_text(
            f"✅ *[{idx}/{total}]* Extracted *{q_count}* questions from `{file_name}`",
            parse_mode="Markdown"
        )
        await _send_outputs(update, ctx, mode)

    await update.message.reply_text(
        f"🏁 *Done!* Processed *{total}* file(s) with `{mode}` output.",
        parse_mode="Markdown"
    )


# ── Internal: build & send output files for current quiz_data ─────────────────
async def _send_outputs(update, ctx, mode):
    quiz_data = ctx.user_data.get(KEY_QUIZ_DATA)
    test_name = ctx.user_data.get(KEY_TEST_NAME, "quiz")
    safe_name = test_name.replace(" ", "_").lower()[:60]
    uid       = update.effective_user.id

    if not quiz_data:
        await update.message.reply_text("❌ No quiz data. Please start over.")
        return

    try:
        if mode in ("gangleader", "both"):
            gl_html = build_html(quiz_data, brand="gangleader")
            gl_path = os.path.join(TEMP_DIR, f"{uid}_{safe_name}_gangleader.html")
            Path(gl_path).write_text(gl_html, encoding="utf-8")
            await update.message.reply_document(
                document=open(gl_path, "rb"),
                filename=f"{safe_name}_gangleader.html",
                caption=f"🏆 *GangLeader* — {test_name}",
                parse_mode="Markdown"
            )

        if mode in ("sienova", "both"):
            sv_html = build_html(quiz_data, brand="sienova")
            sv_path = os.path.join(TEMP_DIR, f"{uid}_{safe_name}_sienova.html")
            Path(sv_path).write_text(sv_html, encoding="utf-8")
            await update.message.reply_document(
                document=open(sv_path, "rb"),
                filename=f"{safe_name}_sienova.html",
                caption=f"📘 *Sienova* — {test_name}",
                parse_mode="Markdown"
            )

        if mode in ("json", "both"):
            json_path = os.path.join(TEMP_DIR, f"{uid}_{safe_name}.json")
            Path(json_path).write_text(
                json.dumps(quiz_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            await update.message.reply_document(
                document=open(json_path, "rb"),
                filename=f"{safe_name}.json",
                caption=f"📄 *JSON* — {test_name}",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.exception("Error generating output for %s", test_name)
        await update.message.reply_text(f"❌ Error for `{test_name}`: {e}", parse_mode="Markdown")
