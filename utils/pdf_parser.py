"""
PDF Quiz Parser — v3
Handles:
1. Font-encoded PDFs where extract_text() returns None → word-join fallback
2. Direction lines (bold instruction) shown separately from question stem
3. Reading comprehension passages shown as context, not merged into question
4. Chart/graph images EXTRACTED and embedded as base64 in question text
5. Watermark noise stripped from within option text
6. Page-break artifacts removed
7. Missing options detected (watermark covered text)
"""

import re
import io
import base64
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

LABELS = ["A", "B", "C", "D", "E", "F"]

# ── Noise patterns ─────────────────────────────────────────────────────────────
_HEADER_NOISE = re.compile(
    r'^(IBPS\s+PO.*|Page\s+\d+\s+Of\s+\d+.*|@JethaBanker.*|Guidely.*|'
    r'Get it on.*|Google Play.*|\(Day-\d+\))\s*$',
    re.MULTILINE | re.IGNORECASE
)

# Inline watermarks (partial, overlapping text)
_INLINE_WM = re.compile(
    r'@(?:Jetha|Jeth|Jet|Je|J)[\w. ]*(?:Banker|anker|nker|ker|er)?\b',
    re.IGNORECASE
)

# Direction/instruction line patterns (these are the bold intro lines)
_DIRECTION_PATTERNS = [
    r'^In (?:each|the following)',
    r'^Read the following',
    r'^Study the following',
    r'^Directions?\s*:',
    r'^What (?:approximate )?value',
    r'^Find the (?:wrong|missing)',
    r'^For the following',
    r'^Choose the (?:correct|most|option)',
]
_IS_DIRECTION = re.compile(
    '|'.join(_DIRECTION_PATTERNS), re.IGNORECASE
)

# Chart / image reference in text
_CHART_REF = re.compile(
    r'\b(pie chart|bar graph|bar chart|line graph|table given|'
    r'histogram|venn diagram|data given below|graph given below|'
    r'chart given below|refer (?:to )?(?:the )?(?:table|chart|graph|figure))\b',
    re.IGNORECASE
)

# ── Main entry ─────────────────────────────────────────────────────────────────

def parse_pdf(pdf_path: str, test_name: str | None = None) -> dict | None:
    """Parse an IBPS-style quiz PDF. Returns quiz_data dict or None."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed.")
        return None

    try:
        pages_text, page_images = _extract_all(pdf_path)
    except Exception as e:
        logger.error("Failed to read PDF %s: %s", pdf_path, e)
        return None

    full_text = "\n".join(pages_text)

    if not full_text or len(full_text.strip()) < 100:
        logger.warning("No text extracted from %s", pdf_path)
        return None

    exp_idx = _find_explanations(full_text)
    q_raw = full_text[:exp_idx] if exp_idx != -1 else full_text
    ex_raw = full_text[exp_idx:] if exp_idx != -1 else ""

    questions  = _parse_questions(q_raw, page_images)
    answer_map = _parse_explanations(ex_raw)

    if not questions:
        logger.warning("No questions found in %s", pdf_path)
        return None

    for q in questions:
        ans = answer_map.get(q["question_number"], {})
        q["correct_answer"] = ans.get("correct_answer")
        q["solution"]       = _sanitize(ans.get("solution", ""))

    name = test_name or Path(pdf_path).stem.replace("_", " ").strip()
    return {
        "test_name":       name,
        "total_questions": len(questions),
        "extracted_at":    datetime.now().isoformat(),
        "duration_sec":    20 * 60,
        "questions":       questions,
    }


# ── Extraction ─────────────────────────────────────────────────────────────────

def _extract_all(pdf_path: str):
    """Extract text + chart images. Tries 4 strategies for difficult PDFs."""
    import pdfplumber

    pages_text  = []
    page_images = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):

            # Strategy 1: standard
            text = page.extract_text()

            # Strategy 2: layout mode
            if not text or len(text.strip()) < 20:
                try:
                    text = page.extract_text(layout=True)
                except Exception:
                    text = None

            # Strategy 3: word-box reconstruction (several tolerances)
            if not text or len(text.strip()) < 20:
                for xt in [2, 5, 10]:
                    try:
                        words = page.extract_words(
                            x_tolerance=xt, y_tolerance=3,
                            keep_blank_chars=False, use_text_flow=True
                        )
                        if words:
                            lines = {}
                            for w in words:
                                y = round(w["top"] / 4) * 4
                                lines.setdefault(y, []).append(w["text"])
                            text = "\n".join(
                                " ".join(lines[y]) for y in sorted(lines)
                            )
                            if len((text or "").strip()) >= 20:
                                break
                    except Exception:
                        pass

            # Strategy 4: char-level reconstruction
            if not text or len(text.strip()) < 20:
                try:
                    chars = page.chars
                    if chars:
                        lines = {}
                        for c in chars:
                            ch = c.get("text", "")
                            if not ch.strip():
                                continue
                            y = round(float(c.get("top", 0)) / 5) * 5
                            lines.setdefault(y, []).append(ch)
                        text = "\n".join(
                            "".join(lines[y]) for y in sorted(lines)
                        )
                except Exception:
                    pass

            if text and len(text.strip()) >= 5:
                pages_text.append(text)

            # ── Chart images ──
            charts = []
            for img in page.images:
                w = img.get("width", 0)
                h = img.get("height", 0)
                # Skip header/footer logos (small images near top/bottom)
                top = img.get("top", 0)
                page_h = float(page.height)
                if w < 200 or h < 150:
                    continue
                if top < 50 or top > page_h - 50:
                    continue
                # This looks like a chart — crop & encode
                try:
                    bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
                    cropped = page.crop(bbox)
                    pil_img = cropped.to_image(resolution=120).original
                    buf = io.BytesIO()
                    pil_img.save(buf, format="PNG", optimize=True)
                    b64 = base64.b64encode(buf.getvalue()).decode()
                    charts.append(b64)
                    logger.info("Extracted chart image from page %d (%dx%d)", page_num+1, int(w), int(h))
                except Exception as e:
                    logger.warning("Chart extraction failed page %d: %s", page_num+1, e)

            if charts:
                page_images[page_num] = charts

    return pages_text, page_images


def _find_explanations(text: str) -> int:
    for marker in ["Explanations:", "Explanation:", "EXPLANATIONS:", "EXPLANATION:"]:
        idx = text.find(marker)
        if idx != -1:
            return idx
    return -1


# ── Question parsing ───────────────────────────────────────────────────────────

def _parse_questions(raw: str, page_images: dict) -> list:
    clean = _clean_noise(raw)

    # Split on "N. Questions" markers
    blocks = re.split(r'\n(\d+)\. Questions\n', clean)

    # Flatten page_images into a list in order
    all_charts = []
    for pg in sorted(page_images.keys()):
        all_charts.extend(page_images[pg])
    chart_idx = [0]  # mutable pointer

    questions       = []
    last_direction  = ""   # shared instruction line for a group
    last_passage    = ""   # shared passage for RC questions

    for i in range(1, len(blocks) - 1, 2):
        num  = int(blocks[i])
        body = _clean_page_noise(blocks[i + 1])

        # Extract options first
        options, pre_opts = _extract_options(body)

        if not options:
            # No options = probably a pure instruction block, skip silently
            continue

        # Parse the pre-options text into: direction + passage/context + question stem
        direction, passage, q_stem = _parse_pre_opts(pre_opts)

        # --- Direction line handling ---
        if direction:
            # New direction = new group, reset passage
            last_direction = direction
            last_passage   = ""
        
        # --- Passage handling ---
        if passage:
            last_passage = passage

        # --- Question stem ---
        if not q_stem.strip():
            # Stem is empty — this is a follow-up question using shared context
            q_stem = ""

        # Build the final question_text
        # We store direction, passage, stem separately so the HTML can display them nicely
        # Format: direction||passage||stem  (split by || in builder)
        direction_part = last_direction
        passage_part   = last_passage
        stem_part      = _sanitize(q_stem) if q_stem.strip() else ""

        if not stem_part and not direction_part:
            continue

        # Chart image assignment:
        # Group key = direction + passage together.
        # When this combo changes → new chart group → advance chart index.
        # ALL questions within the same group get the same chart.
        full_context = direction_part + " " + passage_part + " " + stem_part
        has_chart_ref = bool(_CHART_REF.search(full_context))
        chart_b64 = None
        if has_chart_ref and all_charts:
            group_key = (direction_part.strip()[:60], passage_part.strip()[:60])
            last_group = (
                (questions[-1].get("direction","").strip()[:60],
                 questions[-1].get("passage","").strip()[:60])
                if questions else None
            )
            # Advance to next chart only when group_key changes
            if last_group is not None and last_group != group_key:
                if chart_idx[0] < len(all_charts) - 1:
                    chart_idx[0] += 1
            # Give every question in this group the current chart
            if chart_idx[0] < len(all_charts):
                chart_b64 = all_charts[chart_idx[0]]

        questions.append({
            "id":              num,
            "question_number": num,
            "question_text":   stem_part,
            "direction":       _sanitize(direction_part),
            "passage":         _sanitize(passage_part),
            "chart_image":     chart_b64,   # base64 PNG or None
            "marks":           1,
            "correct_answer":  None,
            "options":         options,
            "solution":        "",
        })

    return questions


def _clean_noise(text: str) -> str:
    return _HEADER_NOISE.sub("", text)


def _clean_page_noise(text: str) -> str:
    """Remove page-break artifacts that land mid-question."""
    text = re.sub(r'\n\(Day-\d+\)\n', '\n', text)
    text = re.sub(r'\nPage\s+\d+\s+Of\s+\d+\n', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\n@JethaBanker\n?', '\n', text)
    text = re.sub(r'\nIBPS PO Prelims PDF Course \d+\n', '\n', text)
    text = re.sub(r'\nIBPS PO Prelims \d+ .*?\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_options(body: str) -> tuple:
    """Extract lettered options (a. / b. ...) from question body."""
    first_opt = re.search(r'\n[a-e]\. ', body)
    if not first_opt:
        return [], body

    pre  = body[:first_opt.start()].strip()
    opts = body[first_opt.start():]

    raw_opts = re.findall(
        r'\n([a-e])\. (.+?)(?=\n[a-e]\. |\Z)',
        "\n" + opts,
        re.DOTALL
    )

    seen    = set()
    options = []
    for lbl, txt in raw_opts:
        lbl = lbl.upper()
        if lbl in seen:
            continue
        seen.add(lbl)
        # Strip watermarks and page noise from within option text
        txt = _clean_page_noise(txt)
        txt = _INLINE_WM.sub("", txt)
        txt = txt.replace("\n", " ").strip()
        txt = re.sub(r'\s{2,}', ' ', txt)
        if txt:
            options.append({"label": lbl, "text": _sanitize(txt)})

    # Detect missing options (covered by watermark) and fill placeholders
    if 2 <= len(options) < 5:
        present = {o["label"] for o in options}
        expected = LABELS[:len(options) + 1]
        for exp in expected:
            if exp not in present:
                idx = LABELS.index(exp)
                options.insert(idx, {"label": exp, "text": "[Text missing in PDF]"})
                present.add(exp)

    return options, pre


# Passage detection: long block of text before first "What/Which/Find" stem
_PASSAGE_START = re.compile(
    r'^(?:Filmmaking|In today|The following|[A-Z][a-z].*(?:is|are|was|were|has|have))',
    re.MULTILINE
)

def _parse_pre_opts(text: str) -> tuple:
    """
    Split pre-options text into (direction, passage, question_stem).
    direction = bold instruction line (e.g. "In the following questions...")
    passage   = RC passage body
    stem      = actual question being asked
    """
    lines = [l for l in text.split("\n") if l.strip()]

    direction_lines = []
    passage_lines   = []
    stem_lines      = []

    state = "direction"  # start expecting direction

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if state == "direction":
            if _IS_DIRECTION.match(stripped) or stripped.startswith("If no improvement"):
                direction_lines.append(stripped)
            elif stripped.startswith("Note:"):
                direction_lines.append(stripped)
            elif stripped.startswith("Word:") or stripped.startswith('"'):
                direction_lines.append(stripped)
            elif re.match(r'^\(I\)', stripped):
                # sentence-based word usage — these are part of the question body
                stem_lines.append(stripped)
                state = "stem"
            else:
                # Check if this is the start of a passage
                if _looks_like_passage(stripped, lines):
                    state = "passage"
                    passage_lines.append(stripped)
                else:
                    state = "stem"
                    stem_lines.append(stripped)

        elif state == "passage":
            # Everything up to the actual question stem is passage
            # Question stems usually start with "What", "Which", "Find", "How", blanks
            if _looks_like_stem(stripped):
                state = "stem"
                stem_lines.append(stripped)
            else:
                passage_lines.append(stripped)

        elif state == "stem":
            stem_lines.append(stripped)

    return (
        " ".join(direction_lines).strip(),
        " ".join(passage_lines).strip(),
        " ".join(stem_lines).strip(),
    )


def _looks_like_passage(line: str, all_lines: list) -> bool:
    """Heuristic: is this line the start of an RC passage?"""
    # If there are many lines before the options, and the line looks like prose
    # (doesn't end with ? and is a long sentence)
    if len(line) < 40:
        return False
    if line.endswith("?"):
        return False
    if re.match(r'^(What|Which|Find|How|Why|When|Where|Who)', line):
        return False
    if re.match(r'^The|^A |^An |^In |^[A-Z][a-z]', line):
        return len(all_lines) > 4  # only treat as passage if there's a lot of text
    return False


def _looks_like_stem(line: str) -> bool:
    """Heuristic: does this line look like the actual question being asked?"""
    return bool(re.match(
        r'^(What|Which|Find|How|Why|When|Where|Who|'
        r'The word|Fill in|According|Modern|Why is|What is the)',
        line, re.IGNORECASE
    ))


# ── Explanation parsing ────────────────────────────────────────────────────────

def _parse_explanations(raw: str) -> dict:
    if not raw.strip():
        return {}

    clean = _clean_noise(raw)
    blocks = re.split(r'\n(\d+)\. Questions\n', clean)

    result = {}
    for i in range(1, len(blocks) - 1, 2):
        num  = int(blocks[i])
        body = _clean_page_noise(blocks[i + 1].strip())

        ans_match = re.search(r'Answer:\s*([A-Ea-e])', body)
        letter = ans_match.group(1).upper() if ans_match else None

        lines = body.split("\n")
        sol_lines = []
        found = False
        for line in lines:
            if not found and re.search(r'Answer:\s*[A-Ea-e]', line):
                found = True
                continue
            if found:
                s = line.strip()
                if not s:
                    continue
                if re.match(r'^(Analysis of Other Options|Option Analysis|Let table)', s, re.IGNORECASE):
                    break  # stop before option-by-option analysis
                sol_lines.append(s)
                if len(sol_lines) >= 4:
                    break

        result[num] = {
            "correct_answer": letter,
            "solution":       " ".join(sol_lines),
        }

    return result


# ── Sanitize ───────────────────────────────────────────────────────────────────

def _sanitize(text: str) -> str:
    """Strip control chars, collapse whitespace — safe for JS embedding."""
    import unicodedata
    result = []
    for c in (text or ""):
        if c in ("\n", "\r", "\t"):
            result.append(" ")
        elif unicodedata.category(c) == "Cc":
            pass
        else:
            result.append(c)
    return " ".join("".join(result).split())
