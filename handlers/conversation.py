"""
Conversation flow — supports:
- /extract + /both : batch HTML files → extract via Playwright → output HTMLs
- /fromjson        : JSON file/text → output HTMLs
- /pdf             : batch PDF files → parse directly (no Playwright) → output HTMLs
All flows share the same mode selection and output logic.
"""

import os
import json
import logging
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
BATCH_COLLECTING  = 4

# Context keys
KEY_MODE      = "flow_mode"   # "extract"|"both"|"fromjson"|"pdf"
KEY_QUIZ_DATA = "quiz_data"
KEY_TEST_NAME = "test_name"
KEY_BATCH     = "batch_files" # list of (path, filename)

MODE_KEYBOARD = ReplyKeyboardMarkup(
    [["gangleader", "sienova"], ["both", "json"]],
    one_time_keyboard=True, resize_keyboard=True,
)

os.makedirs(TEMP_DIR, exist_ok=True)


# ── /cancel ───────────────────────────────────────────────────────────────────
@require_auth
async def cancel_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── Entry points (called from generate.py) ────────────────────────────────────
@require_auth
async def extract_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.update({KEY_MODE: "extract", KEY_BATCH: []})
    await update.message.reply_text(
        "📤 *Extract Mode*\n\nSend one or more quiz *HTML* files.\nType *done* when finished.",
        parse_mode="Markdown"
    )
    return BATCH_COLLECTING


@require_auth
async def html_to_both_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.update({KEY_MODE: "both", KEY_BATCH: []})
    await update.message.reply_text(
        "⚡ *Both Mode*\n\nSend one or more quiz *HTML* files.\nType *done* — I'll generate GangLeader + Sienova + JSON for each.",
        parse_mode="Markdown"
    )
    return BATCH_COLLECTING


@require_auth
async def json_to_html_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.update({KEY_MODE: "fromjson", KEY_BATCH: []})
    await update.message.reply_text(
        "📋 *JSON → HTML Mode*\n\nSend a `.json` file or paste JSON text.",
        parse_mode="Markdown"
    )
    return WAITING_FOR_JSON


@require_auth
async def pdf_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.update({KEY_MODE: "pdf", KEY_BATCH: []})
    await update.message.reply_text(
        "📄 *PDF Mode*\n\n"
        "Send one or more IBPS-style quiz *PDF* files.\n"
        "I'll extract questions, options, answers & solutions — no Playwright needed.\n\n"
        "Type *done* when finished sending PDFs.",
        parse_mode="Markdown"
    )
    return BATCH_COLLECTING


# ── Batch collect (HTML or PDF depending on mode) ─────────────────────────────
@require_auth
async def batch_collect_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Collect files. 'done' triggers processing."""

    # Text → "done" signal
    if update.message.text:
        cmd = update.message.text.strip().lower()
        if cmd in ("done", "start", "go", "process"):
            return await _start_batch(update, ctx)
        await update.message.reply_text(
            "Send files then type *done* to process.",
            parse_mode="Markdown"
        )
        return BATCH_COLLECTING

    doc = update.message.document
    if not doc:
        return BATCH_COLLECTING

    mode = ctx.user_data.get(KEY_MODE, "extract")
    fname = doc.file_name.lower()

    # Validate extension
    if mode == "pdf":
        if not fname.endswith(".pdf"):
            await update.message.reply_text(f"⚠️ `{doc.file_name}` is not a PDF — skipped.", parse_mode="Markdown")
            return BATCH_COLLECTING
    else:
        if not fname.endswith(".html"):
            await update.message.reply_text(f"⚠️ `{doc.file_name}` is not an HTML file — skipped.", parse_mode="Markdown")
            return BATCH_COLLECTING

    # Download
    tmp_path = os.path.join(TEMP_DIR, f"{update.effective_user.id}_{doc.file_name}")
    tg_file = await ctx.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(tmp_path)

    batch = ctx.user_data.setdefault(KEY_BATCH, [])
    batch.append((tmp_path, doc.file_name))

    ext = "PDF" if mode == "pdf" else "HTML"
    await update.message.reply_text(
        f"✅ `{doc.file_name}` queued ({len(batch)} {ext}{'s' if len(batch)>1 else ''} so far)\n"
        f"Send more or type *done* to process.",
        parse_mode="Markdown"
    )
    return BATCH_COLLECTING


async def _start_batch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    batch = ctx.user_data.get(KEY_BATCH, [])
    if not batch:
        await update.message.reply_text("❌ No files queued. Send files first.")
        return BATCH_COLLECTING

    flow = ctx.user_data.get(KEY_MODE, "extract")

    if flow == "both":
        await update.message.reply_text(
            f"⚙️ Processing *{len(batch)}* file(s) → GangLeader + Sienova + JSON...",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
        )
        await _process_batch(update, ctx, "both", batch)
        ctx.user_data.clear()
        return ConversationHandler.END

    if flow == "pdf":
        # Ask output mode
        await update.message.reply_text(
            f"📋 *{len(batch)}* PDF(s) queued.\n\nChoose output format for all:",
            parse_mode="Markdown", reply_markup=MODE_KEYBOARD
        )
        return WAITING_FOR_MODE

    # extract mode — ask output mode
    await update.message.reply_text(
        f"📋 *{len(batch)}* file(s) queued.\n\nChoose output format:",
        parse_mode="Markdown", reply_markup=MODE_KEYBOARD
    )
    return WAITING_FOR_MODE


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
        raw_json = Path(tmp_path).read_text(encoding="utf-8")
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
    ctx.user_data[KEY_BATCH] = []

    await update.message.reply_text(
        f"✅ Loaded *{len(quiz_data.get('questions', []))}* questions.\n\nChoose output format:",
        parse_mode="Markdown", reply_markup=MODE_KEYBOARD
    )
    return WAITING_FOR_MODE


# ── Mode selected → process ───────────────────────────────────────────────────
@require_auth
async def generate_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mode = update.message.text.strip().lower()
    if mode not in {"gangleader", "sienova", "both", "json"}:
        await update.message.reply_text(
            "Choose: `gangleader`, `sienova`, `both`, or `json`",
            parse_mode="Markdown", reply_markup=MODE_KEYBOARD
        )
        return WAITING_FOR_MODE

    await update.message.reply_text(
        f"⚙️ Generating `{mode}` output...",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )

    batch = ctx.user_data.get(KEY_BATCH, [])
    flow  = ctx.user_data.get(KEY_MODE, "extract")

    if batch:
        await _process_batch(update, ctx, mode, batch)
    else:
        await _send_outputs(update, ctx, mode)

    ctx.user_data.clear()
    return ConversationHandler.END


# ── Process a batch of files ──────────────────────────────────────────────────
async def _process_batch(update, ctx, mode, batch):
    flow  = ctx.user_data.get(KEY_MODE, "extract")
    total = len(batch)

    for idx, (tmp_path, file_name) in enumerate(batch, 1):
        await update.message.reply_text(
            f"📄 *[{idx}/{total}]* Processing `{file_name}`...",
            parse_mode="Markdown"
        )

        # Extract quiz data
        if flow == "pdf":
            from utils.pdf_parser import parse_pdf
            test_name = _name_from_file(file_name)
            quiz_data = parse_pdf(tmp_path, test_name)
        else:
            quiz_data = await extract_quiz_from_html(tmp_path)

        if not quiz_data:
            await update.message.reply_text(
                f"❌ *[{idx}/{total}]* Failed to extract from `{file_name}` — skipped.",
                parse_mode="Markdown"
            )
            continue

        q_count = len(quiz_data.get("questions", []))
        await update.message.reply_text(
            f"✅ *[{idx}/{total}]* Extracted *{q_count}* questions from `{file_name}`",
            parse_mode="Markdown"
        )

        ctx.user_data[KEY_QUIZ_DATA] = quiz_data
        ctx.user_data[KEY_TEST_NAME] = quiz_data.get("test_name", _name_from_file(file_name))
        await _send_outputs(update, ctx, mode)

    await update.message.reply_text(
        f"🏁 *Done!* Processed *{total}* file(s).",
        parse_mode="Markdown"
    )


# ── Build & send output files ─────────────────────────────────────────────────
async def _send_outputs(update, ctx, mode):
    quiz_data = ctx.user_data.get(KEY_QUIZ_DATA)
    test_name = ctx.user_data.get(KEY_TEST_NAME, "quiz")
    safe_name = re.sub(r'[^a-z0-9]+', '_', test_name.lower())[:60]
    uid       = update.effective_user.id

    if not quiz_data:
        await update.message.reply_text("❌ No quiz data. Please start over.")
        return

    try:
        if mode in ("gangleader", "both"):
            html = build_html(quiz_data, brand="gangleader")
            p = os.path.join(TEMP_DIR, f"{uid}_{safe_name}_gangleader.html")
            Path(p).write_text(html, encoding="utf-8")
            await update.message.reply_document(
                document=open(p, "rb"),
                filename=f"{safe_name}_gangleader.html",
                caption=f"🏆 *GangLeader* — {test_name}",
                parse_mode="Markdown"
            )

        if mode in ("sienova", "both"):
            html = build_html(quiz_data, brand="sienova")
            p = os.path.join(TEMP_DIR, f"{uid}_{safe_name}_sienova.html")
            Path(p).write_text(html, encoding="utf-8")
            await update.message.reply_document(
                document=open(p, "rb"),
                filename=f"{safe_name}_sienova.html",
                caption=f"📘 *Sienova* — {test_name}",
                parse_mode="Markdown"
            )

        if mode in ("json", "both"):
            p = os.path.join(TEMP_DIR, f"{uid}_{safe_name}.json")
            Path(p).write_text(
                json.dumps(quiz_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            await update.message.reply_document(
                document=open(p, "rb"),
                filename=f"{safe_name}.json",
                caption=f"📄 *JSON* — {test_name}",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.exception("Error generating output for %s", test_name)
        await update.message.reply_text(
            f"❌ Error for `{test_name}`: {e}", parse_mode="Markdown"
        )


# ── Kept for legacy single-file path ─────────────────────────────────────────
@require_auth
async def file_received_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith(".html"):
        await update.message.reply_text("⚠️ Only `.html` files accepted here.")
        return WAITING_FOR_FILE

    tmp_path = os.path.join(TEMP_DIR, f"{update.effective_user.id}_{doc.file_name}")
    tg_file = await ctx.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(tmp_path)

    await update.message.reply_text("🔍 Extracting quiz data... (10-20s)")
    quiz_data = await extract_quiz_from_html(tmp_path)

    if not quiz_data:
        await update.message.reply_text("❌ Could not extract `quizData`. Ensure the file has a `quizData` JS variable.", parse_mode="Markdown")
        return ConversationHandler.END

    test_name = _name_from_file(doc.file_name)
    ctx.user_data[KEY_QUIZ_DATA] = quiz_data
    ctx.user_data[KEY_TEST_NAME] = test_name
    ctx.user_data[KEY_BATCH] = []

    if ctx.user_data.get(KEY_MODE) == "both":
        await update.message.reply_text(f"✅ Extracted *{len(quiz_data['questions'])}* questions. Generating...", parse_mode="Markdown")
        await _send_outputs(update, ctx, "both")
        ctx.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ Extracted *{len(quiz_data['questions'])}* questions. Choose output:",
        parse_mode="Markdown", reply_markup=MODE_KEYBOARD
    )
    return WAITING_FOR_MODE


def _name_from_file(filename: str) -> str:
    import re as _re
    name = _re.sub(r'\.(html|pdf|json)$', '', filename, flags=_re.IGNORECASE)
    name = name.replace("_", " ").replace("-", " ").strip()
    return name


import re  # needed by _send_outputs
