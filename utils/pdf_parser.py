"""
PDF Quiz Parser — v5
- Extracts **bold** text using char-level font analysis
- Correctly handles standalone word problems (no shared direction/passage)
- Detects DI groups (pie chart / bar graph) vs standalone questions
- Watermark removal, page-noise stripping
"""

import re, io, base64, logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
LABELS = ["A","B","C","D","E","F"]

_HEADER_NOISE = re.compile(
    r'^(IBPS\s+PO.*|Page\s+\d+\s+Of\s+\d+.*|@JethaBanker.*|'
    r'Guidely.*|Get it on.*|Google Play.*|\(Day-\d+\))\s*$',
    re.MULTILINE | re.IGNORECASE
)
_INLINE_WM = re.compile(r'\*\*@[^*]+\*\*|@(?:\w+\.?\s*){1,4}(?:Banker|anker|nker)', re.IGNORECASE)

_CHART_REF = re.compile(
    r'\b(pie chart|bar graph|bar chart|line graph|table given|histogram|'
    r'venn diagram|data given below|graph given below|chart given below|'
    r'refer (?:to )?(?:the )?(?:table|chart|graph|figure))\b', re.IGNORECASE
)

_DIR_START = re.compile(
    r'^(In (?:each|the following)|Read the following|Study the following|'
    r'Directions?\s*:|What (?:approximate )?value|Find the (?:wrong|missing))',
    re.IGNORECASE
)
_DIR_CONTINUATION = re.compile(
    r'^(best expresses|that correctly|such that|the pair of|If no improvement|'
    r'appropriate option|contextually|sentence grammatically|option that best|'
    r'the option that)',
    re.IGNORECASE
)
_WORD_LABEL   = re.compile(r'^\*?\*?Word:\s*["\u201c](.+?)["\u201d]\*?\*?', re.IGNORECASE)
_STATEMENT    = re.compile(r'^\((I{1,3}|IV|V)\)\s+')
_STEM_PATTERN = re.compile(
    r'^(What|Which|Find|How|Why|When|Where|Who|According|The word|Fill in|'
    r'Modern|Why is|What is the|Choose|Identify)',
    re.IGNORECASE
)


def parse_pdf(pdf_path: str, test_name: str | None = None) -> dict | None:
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed"); return None

    try:
        pages_text, page_images = _extract_all(pdf_path)
    except Exception as e:
        logger.error("Failed to read %s: %s", pdf_path, e); return None

    full_text = "\n".join(pages_text)
    if not full_text or len(full_text.strip()) < 100:
        logger.warning("No text extracted from %s", pdf_path); return None

    exp_idx   = _find_explanations(full_text)
    q_raw     = full_text[:exp_idx] if exp_idx != -1 else full_text
    ex_raw    = full_text[exp_idx:] if exp_idx != -1 else ""

    questions  = _parse_questions(q_raw, page_images)
    answer_map = _parse_explanations(ex_raw)

    if not questions:
        logger.warning("No questions found in %s", pdf_path); return None

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
    import pdfplumber
    pages_text, page_images = [], {}

    with pdfplumber.open(pdf_path) as pdf:
        for pn, page in enumerate(pdf.pages):
            # Try rich text extraction first (preserves bold markers)
            text = _extract_rich_text(page)

            # Fallbacks for scanned/encoded PDFs
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

            if text and len(text.strip()) >= 5:
                pages_text.append(text)

            # Chart images (skip logos/headers)
            charts = []
            for img in page.images:
                w, h   = img.get("width",0), img.get("height",0)
                top    = img.get("top",0)
                page_h = float(page.height)
                if w < 200 or h < 150: continue
                if top < 50 or top > page_h - 50: continue
                try:
                    bbox    = (img["x0"], img["top"], img["x1"], img["bottom"])
                    pil_img = page.crop(bbox).to_image(resolution=120).original
                    buf     = io.BytesIO()
                    pil_img.save(buf, format="PNG", optimize=True)
                    charts.append(base64.b64encode(buf.getvalue()).decode())
                except Exception as e:
                    logger.warning("Chart extract failed p%d: %s", pn+1, e)
            if charts:
                page_images[pn] = charts

    return pages_text, page_images


def _extract_rich_text(page) -> str:
    """Extract page text with **bold** markers using char-level font data."""
    chars = page.chars
    if not chars:
        return page.extract_text() or ""

    # Group chars into lines by y-position (2pt buckets)
    lines = {}
    for c in chars:
        y = round(c.get("top", 0) / 2) * 2
        lines.setdefault(y, []).append(c)

    result_lines = []
    for y in sorted(lines.keys()):
        line_chars = sorted(lines[y], key=lambda c: c.get("x0", 0))
        segments   = []
        cur_bold   = None
        cur_text   = []

        for c in line_chars:
            ch       = c.get("text", "")
            if not ch: continue
            fontname = c.get("fontname", "")
            is_bold  = "Bold" in fontname or "bold" in fontname

            if cur_bold is None:
                cur_bold = is_bold
                cur_text.append(ch)
            elif is_bold == cur_bold:
                cur_text.append(ch)
            else:
                seg = "".join(cur_text)
                segments.append(f"**{seg}**" if cur_bold and seg.strip() else seg)
                cur_bold = is_bold
                cur_text = [ch]

        if cur_text:
            seg = "".join(cur_text)
            segments.append(f"**{seg}**" if cur_bold and seg.strip() else seg)

        result_lines.append("".join(segments))

    return "\n".join(result_lines)


def _find_explanations(text: str) -> int:
    for m in ["Explanations:", "Explanation:", "EXPLANATIONS:", "EXPLANATION:"]:
        i = text.find(m)
        if i != -1: return i
    return -1


# ── Question parsing ───────────────────────────────────────────────────────────

def _parse_questions(raw: str, page_images: dict) -> list:
    clean = _clean_noise(raw)
    # Normalize question number markers: "**1.** Questions" → "1. Questions"
    # Bold markers wrap the number but the splitter needs plain text
    clean = re.sub(r'\*\*(\d+)\.\*\*\s*Questions', r'\1. Questions', clean)
    clean = re.sub(r'\*\*(\d+\.\s*Questions)\*\*', r'\1', clean)
    blocks = re.split(r'\n(\d+)\. Questions\n', clean)

    all_charts = []
    for pg in sorted(page_images):
        all_charts.extend(page_images[pg])
    chart_ptr = [0]

    questions      = []
    shared_dir     = ""
    shared_passage = ""

    for i in range(1, len(blocks)-1, 2):
        num  = int(blocks[i])
        body = _clean_page_noise(blocks[i+1])

        options, pre = _extract_options(body)
        if not options:
            continue

        direction, word_label, statements, passage, stem = _split_pre(pre)

        # ── Direction / passage group management ────────────────────────────
        # Simple rule:
        # - If block has a direction → update shared_dir, update shared_passage if has passage
        # - If block has direction but no passage → clear shared_passage (new non-DI group)
        # - If block has no direction → this is a continuation; keep shared context as-is
        #   UNLESS stem is long and self-contained AND no chart ref → then clear shared

        if direction:
            shared_dir = direction
            if passage:
                shared_passage = passage   # DI group: new data set
            elif not _CHART_REF.search(stem + " " + passage):
                shared_passage = ""        # non-DI group: clear passage
        # else: no direction in block → keep shared_dir and shared_passage unchanged

        # If stem is clearly standalone (long + no chart context + no shared chart passage)
        if not direction and not passage and stem:
            if not _CHART_REF.search(shared_passage) and len(stem) > 80:
                shared_dir     = ""
                shared_passage = ""

        effective_dir     = shared_dir
        effective_passage = shared_passage
        # Override with block-specific if present
        if direction: effective_dir     = direction
        if passage:   effective_passage = passage

        # ── Build question text ─────────────────────────────────────────────
        if word_label:
            q_text = f'Word: "{word_label}" | ' + " | ".join(statements)
        elif statements:
            q_text = " | ".join(statements)
            if stem: q_text = stem + " | " + q_text
        else:
            q_text = stem

        if not q_text.strip() and not effective_dir:
            continue

        # ── Chart assignment ────────────────────────────────────────────────
        full_ctx  = effective_dir + " " + effective_passage + " " + q_text
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

        # Strip ** markers when used for emphasis (keep) but
        # remove when the ENTIRE question text is bold (formatting artifact)
        plain_outside_bold = re.sub(r'\*\*[^*]+\*\*', '', q_text).strip()
        all_content_is_bold = (
            not plain_outside_bold and '**' in q_text
        )
        if all_content_is_bold:
            q_text = re.sub(r'\*\*', '', q_text).strip()

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
    """Split pre-options block → (direction, word_label, statements, passage, stem)."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    direction_lines = []
    word_label      = None
    statements      = []
    passage_lines   = []
    stem_lines      = []

    i = 0
    while i < len(lines):
        line = lines[i]
        # Strip bold markers for matching (keep original for display)
        plain = re.sub(r'\*\*', '', line).strip()

        # Direction start
        if not direction_lines and _DIR_START.match(plain):
            direction_lines.append(line)
            i += 1
            while i < len(lines):
                nxt       = lines[i]
                nxt_plain = re.sub(r'\*\*', '', nxt).strip()
                if _DIR_CONTINUATION.match(nxt_plain):
                    direction_lines.append(nxt)
                    i += 1
                else:
                    break
            continue

        # Word label
        wm = _WORD_LABEL.match(plain)
        if wm:
            word_label = wm.group(1)
            i += 1
            continue

        # Statement lines (I) / (II) / (III)
        if _STATEMENT.match(plain):
            statements.append(line)
            i += 1
            continue

        # Passage: long prose before a stem line
        if (not word_label and not statements and not stem_lines
                and _looks_like_passage(plain, lines[i+1:])):
            passage_lines.append(line)
            i += 1
            while i < len(lines):
                nxt_plain = re.sub(r'\*\*', '', lines[i]).strip()
                if _STEM_PATTERN.match(nxt_plain) or nxt_plain.startswith("Fill in"):
                    break
                passage_lines.append(lines[i])
                i += 1
            continue

        # Note: lines (extra instructions mid-block)
        if plain.lower().startswith("note:"):
            direction_lines.append(line)
            i += 1
            continue

        stem_lines.append(line)
        i += 1

    return (
        " ".join(re.sub(r'\*\*', '', l) for l in direction_lines).strip(),
        word_label,
        [re.sub(r'\*\*', '', s).strip() for s in statements],  # keep plain for stem
        " ".join(re.sub(r'\*\*', '', l) for l in passage_lines).strip(),
        " ".join(stem_lines).strip(),   # keep **bold** in stem
    )


def _looks_like_passage(line: str, remaining: list) -> bool:
    if len(line) < 50: return False
    if line.endswith("?"): return False
    if _STEM_PATTERN.match(line): return False
    if _DIR_START.match(line): return False
    return len(remaining) >= 3


def _clean_noise(text: str) -> str:
    return _HEADER_NOISE.sub("", text)


def _clean_page_noise(text: str) -> str:
    text = re.sub(r'\n\(Day-\d+\)\n', '\n', text)
    text = re.sub(r'\nPage\s+\d+\s+Of\s+\d+\n', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\nIBPS\s+PO[^\n]+\n', '\n', text)
    text = re.sub(r'\n@JethaBanker\n?', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_options(body: str):
    # Match both "a. text" (with space) and "a.text" (no space, from rich-text extraction)
    first = re.search(r'\n[a-e]\.\s?', body)
    if not first:
        return [], body

    pre  = body[:first.start()].strip()
    opts = body[first.start():]

    raw = re.findall(r'\n([a-e])\.\s?(.+?)(?=\n[a-e]\.\s?|\Z)', "\n"+opts, re.DOTALL)

    seen, options = set(), []
    for lbl, txt in raw:
        lbl = lbl.upper()
        if lbl in seen: continue
        seen.add(lbl)
        txt = _clean_page_noise(txt)
        txt = _INLINE_WM.sub("", txt)
        # Strip bold markers from options (no need for bold in options)
        txt = re.sub(r'\*\*', '', txt).replace("\n"," ").strip()
        txt = re.sub(r'\s{2,}', ' ', txt)
        if txt:
            options.append({"label": lbl, "text": _sanitize(txt)})

    if 2 <= len(options) < 5:
        present = {o["label"] for o in options}
        for exp in LABELS[:len(options)+1]:
            if exp not in present:
                options.insert(LABELS.index(exp), {"label": exp, "text": "[Text missing in PDF]"})
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
        # Strip bold markers from explanations text
        body = re.sub(r'\*\*', '', body)

        ans    = re.search(r'Answer:\s*([A-Ea-e])', body)
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
    """Strip control chars, collapse whitespace — safe for JS. Keeps **bold** markers."""
    import unicodedata
    result = []
    for c in (text or ""):
        if c in ("\n", "\r", "\t"):
            result.append(" ")
        elif unicodedata.category(c) == "Cc":
            pass
        else:
            result.append(c)
    # Collapse whitespace but preserve ** markers
    out = re.sub(r'(?<!\*) {2,}(?!\*)', ' ', "".join(result))
    return out.strip()
