"""
PDF Quiz Parser — Improved
Handles:
- PDFs where extract_text() returns None (fallback to extract_words)
- Group instruction lines (shared across questions)
- Image-based questions (pie chart / bar graph) — noted in text
- Page-break noise inside option lists
- Newline sanitization for safe JS embedding
"""

import re
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Noise patterns ────────────────────────────────────────────────────────────
_HEADER_NOISE = re.compile(
    r'^(IBPS\s+PO.*|Page\s+\d+.*|@JethaBanker.*|Guidely.*|'
    r'Get it on.*|Google Play.*|\(Day-\d+\))\s*$',
    re.MULTILINE | re.IGNORECASE
)

# Image/chart indicators — questions that reference a visual
_CHART_HINT = re.compile(
    r'\b(pie chart|bar graph|bar chart|table|line graph|histogram|'
    r'venn diagram|data given below|refer.*(?:table|chart|graph))\b',
    re.IGNORECASE
)

# Group instruction patterns (shared context for multiple questions)
_GROUP_INSTRUCTION = re.compile(
    r'^(?:study the following|read the following|in (?:each|the following)|'
    r'directions?:|note:|what (?:approximate )?value)',
    re.IGNORECASE
)

LABELS = ["A", "B", "C", "D", "E", "F"]


def parse_pdf(pdf_path: str, test_name: str | None = None) -> dict | None:
    """Parse an IBPS-style PDF quiz. Returns quiz_data dict or None."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed.")
        return None

    try:
        full_text = _extract_text(pdf_path)
    except Exception as e:
        logger.error("Failed to read PDF %s: %s", pdf_path, e)
        return None

    if not full_text or len(full_text.strip()) < 100:
        logger.warning("No text extracted from %s", pdf_path)
        return None

    # Split at Explanations section
    exp_idx = _find_explanations(full_text)
    q_raw = full_text[:exp_idx] if exp_idx != -1 else full_text
    ex_raw = full_text[exp_idx:] if exp_idx != -1 else ""

    questions  = _parse_questions(q_raw)
    answer_map = _parse_explanations(ex_raw)

    if not questions:
        logger.warning("No questions found in %s", pdf_path)
        return None

    # Merge answers
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


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_text(pdf_path: str) -> str:
    """Extract text from PDF, falling back to word-join if needed."""
    import pdfplumber

    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Primary: extract_text()
            text = page.extract_text()

            # Fallback: reconstruct from words (handles some encoded fonts)
            if not text or len(text.strip()) < 20:
                words = page.extract_words(
                    x_tolerance=3, y_tolerance=3,
                    keep_blank_chars=False, use_text_flow=True
                )
                if words:
                    # Group words into lines by y-position
                    lines = {}
                    for w in words:
                        y = round(w["top"])
                        lines.setdefault(y, []).append(w["text"])
                    text = "\n".join(
                        " ".join(lines[y]) for y in sorted(lines)
                    )

            if text:
                pages_text.append(text)

    return "\n".join(pages_text)


def _find_explanations(text: str) -> int:
    for marker in ["Explanations:", "Explanation:", "EXPLANATIONS:", "EXPLANATION:"]:
        idx = text.find(marker)
        if idx != -1:
            return idx
    return -1


# ── Question parsing ──────────────────────────────────────────────────────────

def _parse_questions(raw: str) -> list:
    clean = _clean_noise(raw)

    # Split on "N. Questions" markers
    blocks = re.split(r'\n(\d+)\. Questions\n', clean)
    # [preamble, '1', body1, '2', body2, ...]

    questions = []
    prev_group_instruction = ""   # track shared instruction across questions

    for i in range(1, len(blocks) - 1, 2):
        num  = int(blocks[i])
        body = _clean_page_noise(blocks[i + 1].strip())

        # Extract options
        options, body_without_opts = _extract_options(body)

        if not options:
            # Skip questions with no options (pure instructions or image-only)
            logger.debug("Q%d skipped — no options found", num)
            continue

        # Split question text from any group instruction
        q_text, group_inst = _split_instruction(body_without_opts)

        # If this question has no real text (just repeating group instruction), use the group instruction
        if not q_text.strip() and group_inst:
            q_text = group_inst
        elif group_inst:
            # Store as shared context
            prev_group_instruction = group_inst
            q_text = group_inst + "\n\n" + q_text if q_text.strip() else group_inst
        elif not q_text.strip() and prev_group_instruction:
            # Carry forward the last group instruction (e.g. Q2-Q5 after Q1 sets it)
            q_text = prev_group_instruction + "\n\n" + q_text
        
        # Clean up the question text
        q_text = _sanitize(q_text)

        if not q_text:
            logger.debug("Q%d skipped — empty question text", num)
            continue

        # Note if question references a chart/image
        if _CHART_HINT.search(q_text):
            q_text = q_text + " [Note: Chart/Graph referenced in original — refer to source PDF]"

        questions.append({
            "id":              num,
            "question_number": num,
            "question_text":   q_text,
            "marks":           1,
            "correct_answer":  None,
            "options":         options,
            "solution":        "",
        })

    return questions


def _clean_noise(text: str) -> str:
    """Remove header/footer noise lines."""
    return _HEADER_NOISE.sub("", text)


def _clean_page_noise(text: str) -> str:
    """Remove page-break artifacts that appear mid-question."""
    # Remove lines that are just "(Day-N)" or "Page N Of M" stuck inside content
    text = re.sub(r'\n\(Day-\d+\)\n', '\n', text)
    text = re.sub(r'\nPage\s+\d+\s+Of\s+\d+\n', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\n@JethaBanker\n', '\n', text)
    # Collapse 3+ blank lines to 1
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_options(body: str) -> tuple[list, str]:
    """
    Extract option lines (a. text / b. text ...) from body.
    Returns (options_list, body_without_options).
    """
    # Find first option
    first_opt = re.search(r'\n[a-e]\. ', body)
    if not first_opt:
        return [], body

    text_before = body[:first_opt.start()].strip()
    opts_section = body[first_opt.start():]

    # Extract all options
    raw_opts = re.findall(
        r'\n([a-e])\. (.+?)(?=\n[a-e]\. |\Z)',
        "\n" + opts_section,
        re.DOTALL
    )

    options = []
    seen_labels = set()
    for lbl, txt in raw_opts:
        # Clean page-break artifacts inside option text
        clean_txt = _clean_page_noise(txt)
        clean_txt = clean_txt.replace("\n", " ").strip()
        lbl_upper = lbl.upper()
        if lbl_upper in seen_labels:
            continue
        seen_labels.add(lbl_upper)
        # Aggressively strip any watermark remnants from within option text
        clean_txt = re.sub(r'@[\w.]+\s*(?:\w+\s*){0,3}(?:Banker|anker|aker)', '', clean_txt).strip()
        clean_txt = re.sub(r'\s{2,}', ' ', clean_txt).strip()
        if clean_txt:
            options.append({
                "label": lbl_upper,
                "text":  _sanitize(clean_txt),
            })

    # Detect and fill missing option letters (watermark may have covered one)
    if len(options) >= 2:
        present = [o["label"] for o in options]
        expected = LABELS[:len(present) + len(present)//4 + 1]
        # Find gaps
        for exp_lbl in expected[:len(present)+1]:
            if exp_lbl not in present and len(options) < 5:
                # Insert placeholder at correct position
                idx_insert = LABELS.index(exp_lbl)
                options.insert(idx_insert, {
                    "label": exp_lbl,
                    "text":  "[Option text unavailable in PDF]",
                })
                present = [o["label"] for o in options]

    return options, text_before


def _split_instruction(text: str) -> tuple[str, str]:
    """
    Split shared group instruction from the actual question stem.
    Returns (question_text, instruction_text).
    """
    lines = text.strip().split("\n")
    inst_lines = []
    q_lines = []
    
    in_instruction = True
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_instruction and inst_lines:
                in_instruction = False
            continue
        
        if in_instruction and (_GROUP_INSTRUCTION.match(stripped) or 
                                stripped.startswith("Word:") or
                                stripped.startswith("(I)") or
                                stripped.startswith("Note:")):
            inst_lines.append(stripped)
        else:
            in_instruction = False
            q_lines.append(stripped)

    instruction = " ".join(inst_lines).strip()
    question    = " ".join(q_lines).strip()
    return question, instruction


# ── Explanation parsing ───────────────────────────────────────────────────────

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

        # Solution = everything after "Answer:" line
        lines = body.split("\n")
        sol_lines = []
        found = False
        for line in lines:
            if not found and re.search(r'Answer:\s*[A-Ea-e]', line):
                found = True
                continue
            if found:
                stripped = line.strip()
                # Skip "Analysis of Other Options:" header
                if stripped.lower().startswith("analysis of other"):
                    continue
                if stripped:
                    sol_lines.append(stripped)

        result[num] = {
            "correct_answer": letter,
            "solution":       " ".join(sol_lines[:6]),  # first 6 lines of solution
        }

    return result


# ── Sanitize ──────────────────────────────────────────────────────────────────

def _sanitize(text: str) -> str:
    """Strip control chars, collapse whitespace — safe for JSON in <script>."""
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
