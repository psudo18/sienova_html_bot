"""
PDF Quiz Parser — v4
Clean, precise parsing of IBPS-style PDFs.

Question block structure (raw):
  Direction line 1 (e.g. "In the following questions...")
  Direction line 2 (continuation, e.g. "best expresses...")  ← may wrap across lines
  [Optional: Word: "X"]
  [Optional: (I) stmt (II) stmt (III) stmt]
  [Optional: passage text for RC]
  Actual question sentence / stem
  a. option
  b. option ...
"""

import re, io, base64, logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
LABELS = ["A","B","C","D","E","F"]

# ── Noise ──────────────────────────────────────────────────────────────────────
_HEADER_NOISE = re.compile(
    r'^(IBPS\s+PO.*|Page\s+\d+\s+Of\s+\d+.*|@JethaBanker.*|'
    r'Guidely.*|Get it on.*|Google Play.*|\(Day-\d+\))\s*$',
    re.MULTILINE | re.IGNORECASE
)
_INLINE_WM = re.compile(r'@(?:\w+\.?\s*){1,4}(?:Banker|anker|nker)', re.IGNORECASE)

# ── Chart detection ────────────────────────────────────────────────────────────
_CHART_REF = re.compile(
    r'\b(pie chart|bar graph|bar chart|line graph|table given|histogram|'
    r'venn diagram|data given below|graph given below|chart given below|'
    r'refer (?:to )?(?:the )?(?:table|chart|graph|figure))\b',
    re.IGNORECASE
)

# ── Direction-line detection ───────────────────────────────────────────────────
# These are the bold instruction lines that begin a question group
_DIR_START = re.compile(
    r'^(In (?:each|the following)|Read the following|Study the following|'
    r'Directions?\s*:|What (?:approximate )?value|Find the (?:wrong|missing)|'
    r'For the following)',
    re.IGNORECASE
)

# Lines that are continuations of a direction (not the question stem)
_DIR_CONTINUATION = re.compile(
    r'^(best expresses|that correctly|such that|the pair of|If no improvement|'
    r'appropriate option)',
    re.IGNORECASE
)

# ── Passage detection ──────────────────────────────────────────────────────────
_PASSAGE_INTRO = re.compile(
    r'^(Filmmaking|The (?:economy|government|study|report|passage|article|'
    r'following passage)|In today|Once upon|[A-Z][a-z]{2,}.*(?:is|are|was|were) '
    r'(?:often|widely|generally|commonly|typically))',
    re.IGNORECASE
)
_STEM_PATTERNS = re.compile(
    r'^(What|Which|Find|How|Why|When|Where|Who|According|The word|Fill in|'
    r'Modern|Why is|What is the|Choose|Identify)',
    re.IGNORECASE
)

# ── Word-usage question ────────────────────────────────────────────────────────
_WORD_LABEL = re.compile(r'^Word:\s*["\u201c](.+?)["\u201d]', re.IGNORECASE)
_STATEMENT  = re.compile(r'^\((I{1,3}|IV|V)\)\s+')


def parse_pdf(pdf_path: str, test_name: str | None = None) -> dict | None:
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed")
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
    q_raw   = full_text[:exp_idx] if exp_idx != -1 else full_text
    ex_raw  = full_text[exp_idx:] if exp_idx != -1 else ""

    questions  = _parse_questions(q_raw, page_images)
    answer_map = _parse_explanations(ex_raw)

    if not questions:
        logger.warning("No questions found in %s", pdf_path)
        return None

    for q in questions:
        ans = answer_map.get(q["question_number"], {})
        q["correct_answer"] = ans.get("correct_answer")
        q["solution"]       = _sanitize(ans.get("solution", ""))

    name = test_name or Path(pdf_path).stem.replace("_"," ").strip()
    return {
        "test_name":       name,
        "total_questions": len(questions),
        "extracted_at":    datetime.now().isoformat(),
        "duration_sec":    20 * 60,
        "questions":       questions,
    }


# ── Text extraction ────────────────────────────────────────────────────────────

def _extract_all(pdf_path: str):
    import pdfplumber
    pages_text, page_images = [], {}

    with pdfplumber.open(pdf_path) as pdf:
        for pn, page in enumerate(pdf.pages):
            text = page.extract_text()

            if not text or len(text.strip()) < 20:
                try: text = page.extract_text(layout=True)
                except: text = None

            if not text or len(text.strip()) < 20:
                for xt in [2, 5, 10]:
                    try:
                        words = page.extract_words(x_tolerance=xt, y_tolerance=3,
                                                   keep_blank_chars=False, use_text_flow=True)
                        if words:
                            lines = {}
                            for w in words:
                                y = round(w["top"]/4)*4
                                lines.setdefault(y,[]).append(w["text"])
                            text = "\n".join(" ".join(lines[y]) for y in sorted(lines))
                            if len(text.strip()) >= 20: break
                    except: pass

            if not text or len(text.strip()) < 20:
                try:
                    chars = page.chars
                    if chars:
                        lines = {}
                        for c in chars:
                            ch = c.get("text","")
                            if not ch.strip(): continue
                            y = round(float(c.get("top",0))/5)*5
                            lines.setdefault(y,[]).append(ch)
                        text = "\n".join("".join(lines[y]) for y in sorted(lines))
                except: pass

            if text and len(text.strip()) >= 5:
                pages_text.append(text)

            # Chart images
            charts = []
            for img in page.images:
                w, h = img.get("width",0), img.get("height",0)
                top  = img.get("top",0)
                if w < 200 or h < 150: continue
                if top < 50 or top > float(page.height) - 50: continue
                try:
                    bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
                    pil_img = page.crop(bbox).to_image(resolution=120).original
                    buf = io.BytesIO()
                    pil_img.save(buf, format="PNG", optimize=True)
                    charts.append(base64.b64encode(buf.getvalue()).decode())
                except Exception as e:
                    logger.warning("Chart extract failed page %d: %s", pn+1, e)
            if charts:
                page_images[pn] = charts

    return pages_text, page_images


def _find_explanations(text: str) -> int:
    for m in ["Explanations:", "Explanation:", "EXPLANATIONS:", "EXPLANATION:"]:
        i = text.find(m)
        if i != -1: return i
    return -1


# ── Question parsing ───────────────────────────────────────────────────────────

def _parse_questions(raw: str, page_images: dict) -> list:
    clean  = _clean_noise(raw)
    blocks = re.split(r'\n(\d+)\. Questions\n', clean)

    all_charts = []
    for pg in sorted(page_images):
        all_charts.extend(page_images[pg])
    chart_ptr = [0]   # current chart index

    questions      = []
    shared_dir     = ""   # direction shared across a group
    shared_passage = ""   # RC passage shared across a group

    for i in range(1, len(blocks)-1, 2):
        num  = int(blocks[i])
        body = _clean_page_noise(blocks[i+1])

        # Extract options
        options, pre = _extract_options(body)
        if not options:
            continue

        # Parse pre-options text into parts
        direction, word_label, statements, passage, stem = _split_pre(pre)

        # ── Direction group management ──────────────────────────────────────
        if direction:
            shared_dir     = direction
            shared_passage = ""   # new group resets passage

        if passage:
            shared_passage = passage   # RC: first Q in group sets passage

        effective_dir     = shared_dir
        effective_passage = shared_passage

        # Build final question text
        # For word-usage: word_label + pipe-separated statements (pipe = visual separator)
        if word_label:
            q_text = f'Word: "{word_label}" | ' + " | ".join(statements)
        elif statements:
            q_text = " | ".join(statements)
            if stem:
                q_text = stem + " | " + q_text
        else:
            q_text = stem

        if not q_text.strip() and not effective_dir:
            continue

        # ── Chart assignment ────────────────────────────────────────────────
        full_ctx = effective_dir + " " + effective_passage + " " + q_text
        has_chart = bool(_CHART_REF.search(full_ctx))
        chart_b64 = None

        if has_chart and all_charts:
            group_key = (effective_dir.strip()[:60], effective_passage.strip()[:60])
            last_gk   = (
                (questions[-1].get("direction","")[:60],
                 questions[-1].get("passage","")[:60])
                if questions else None
            )
            if last_gk is not None and last_gk != group_key:
                if chart_ptr[0] < len(all_charts) - 1:
                    chart_ptr[0] += 1
            if chart_ptr[0] < len(all_charts):
                chart_b64 = all_charts[chart_ptr[0]]

        questions.append({
            "id":              num,
            "question_number": num,
            "question_text":   _sanitize(q_text),
            "direction":       _sanitize(effective_dir),
            "passage":         _sanitize(effective_passage),
            "chart_image":     chart_b64,
            "marks":           1,
            "correct_answer":  None,
            "options":         options,
            "solution":        "",
        })

    return questions


def _split_pre(text: str):
    """
    Split pre-options block into:
      direction, word_label, statements (I/II/III), passage, stem
    """
    lines = [l for l in text.split("\n") if l.strip()]

    direction_lines = []
    word_label      = None
    statements      = []
    passage_lines   = []
    stem_lines      = []

    # ── State machine ──────────────────────────────────────────────────────
    # States: dir → word/stmt/stem/passage
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Direction line
        if not direction_lines and _DIR_START.match(line):
            direction_lines.append(line)
            i += 1
            # Consume continuation lines (wrapped direction)
            while i < len(lines):
                nxt = lines[i].strip()
                if (
                    _DIR_CONTINUATION.match(nxt) or
                    nxt.lower().startswith("if no") or
                    nxt.lower().startswith("such that") or
                    nxt.lower().startswith("the pair") or
                    nxt.lower().startswith("appropriate option") or
                    nxt.lower().startswith("contextually") or
                    nxt.lower().startswith("that correctly") or
                    nxt.lower().startswith("sentence grammatically") or
                    nxt.lower().startswith("option that best") or
                    nxt.lower().startswith("the option that")
                ):
                    direction_lines.append(nxt)
                    i += 1
                else:
                    break
            continue

        # Word label line:  Word: "Captivate"
        wm = _WORD_LABEL.match(line)
        if wm:
            word_label = wm.group(1)
            i += 1
            continue

        # Statement lines: (I) ... (II) ... (III) ...
        if _STATEMENT.match(line):
            statements.append(line)
            i += 1
            continue

        # Passage: long flowing prose before an RC stem
        # Detect: if no word_label, no statements yet, line looks like prose
        # and there are many lines remaining (passage spans multiple lines)
        if (
            not word_label and
            not statements and
            not stem_lines and
            _looks_like_passage(line, lines[i+1:])
        ):
            passage_lines.append(line)
            i += 1
            # Keep consuming until we hit a stem line
            while i < len(lines):
                nxt = lines[i].strip()
                if _STEM_PATTERNS.match(nxt) or nxt.startswith("Fill in"):
                    break
                passage_lines.append(nxt)
                i += 1
            continue

        # Everything else = question stem
        stem_lines.append(line)
        i += 1

    direction = " ".join(direction_lines).strip()
    passage   = " ".join(passage_lines).strip()
    stem      = " ".join(stem_lines).strip()

    return direction, word_label, statements, passage, stem


def _looks_like_passage(line: str, remaining: list) -> bool:
    """Heuristic: is this the start of a long RC passage?"""
    if len(line) < 50: return False
    if line.endswith("?"): return False
    if _STEM_PATTERNS.match(line): return False
    if _DIR_START.match(line): return False
    # Passage usually has at least 3 more lines after it
    return len(remaining) >= 3


def _clean_noise(text: str) -> str:
    return _HEADER_NOISE.sub("", text)


def _clean_page_noise(text: str) -> str:
    text = re.sub(r'\n\(Day-\d+\)\n', '\n', text)
    text = re.sub(r'\nPage\s+\d+\s+Of\s+\d+\n', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\nIBPS\s+PO.*?\n', '\n', text)
    text = re.sub(r'\nIBPS\s+PO\s+Prelims\s+\d+.*?\n', '\n', text)
    text = re.sub(r'\n@JethaBanker\n?', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_options(body: str):
    first = re.search(r'\n[a-e]\. ', body)
    if not first:
        return [], body

    pre  = body[:first.start()].strip()
    opts = body[first.start():]

    raw = re.findall(r'\n([a-e])\. (.+?)(?=\n[a-e]\. |\Z)', "\n"+opts, re.DOTALL)

    seen, options = set(), []
    for lbl, txt in raw:
        lbl = lbl.upper()
        if lbl in seen: continue
        seen.add(lbl)
        txt = _clean_page_noise(txt)
        txt = _INLINE_WM.sub("", txt).replace("\n"," ").strip()
        txt = re.sub(r'\s{2,}', ' ', txt)
        if txt:
            options.append({"label": lbl, "text": _sanitize(txt)})

    # Fill missing options (covered by watermark)
    if 2 <= len(options) < 5:
        present = {o["label"] for o in options}
        for exp in LABELS[:len(options)+1]:
            if exp not in present:
                idx = LABELS.index(exp)
                options.insert(idx, {"label": exp, "text": "[Text missing in PDF]"})
                present.add(exp)

    return options, pre


# ── Explanation parsing ────────────────────────────────────────────────────────

def _parse_explanations(raw: str) -> dict:
    if not raw.strip(): return {}
    clean  = _clean_noise(raw)
    blocks = re.split(r'\n(\d+)\. Questions\n', clean)
    result = {}
    for i in range(1, len(blocks)-1, 2):
        num  = int(blocks[i])
        body = _clean_page_noise(blocks[i+1].strip())

        ans = re.search(r'Answer:\s*([A-Ea-e])', body)
        letter = ans.group(1).upper() if ans else None

        lines = body.split("\n")
        sol, found = [], False
        for line in lines:
            if not found and re.search(r'Answer:\s*[A-Ea-e]', line):
                found = True; continue
            if found:
                s = line.strip()
                if not s: continue
                if re.match(r'^(Analysis of Other Options|Option Analysis|Let table)', s, re.IGNORECASE):
                    break
                sol.append(s)
                if len(sol) >= 4: break

        result[num] = {"correct_answer": letter, "solution": " ".join(sol)}
    return result


def _sanitize(text: str) -> str:
    import unicodedata
    result = []
    for c in (text or ""):
        if c in ("\n","\r","\t"):
            result.append(" ")
        elif unicodedata.category(c) == "Cc":
            pass
        else:
            result.append(c)
    return " ".join("".join(result).split())
