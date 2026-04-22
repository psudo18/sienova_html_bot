"""
HTML Builder
- GangLeader: uses gangleader_template.html with {{PLACEHOLDER}} substitution
- Sienova:    uses sienova_template.html — CSS/HTML kept EXACTLY as-is,
              only quiz data + meta text is swapped
"""

import json
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
LABELS = ["A", "B", "C", "D", "E", "F"]
_HERE  = Path(__file__).parent


def _tpl(filename: str) -> str:
    p = _HERE / filename
    if not p.exists():
        raise FileNotFoundError(f"{filename} missing from utils/")
    return p.read_text(encoding="utf-8")


def build_html(quiz_data: dict, brand: str = "gangleader") -> str:
    questions  = quiz_data.get("questions", [])
    test_name  = quiz_data.get("test_name", "Quiz")
    total      = len(questions)
    total_sec  = quiz_data.get("duration_sec", 60 * 60)
    mins       = total_sec // 60

    if brand == "gangleader":
        return _gangleader(questions, test_name, total, total_sec, mins)
    else:
        return _sienova(questions, test_name, total, total_sec, mins)


# ── GangLeader ────────────────────────────────────────────────────────────────
def _gangleader(questions, test_name, total, total_sec, mins):
    out = _tpl("gangleader_template.html")

    items = []
    for q in questions:
        opts = [o["text"] for o in q.get("options", [])]
        cl   = q.get("correct_answer", "A")
        ci   = LABELS.index(cl) if cl in LABELS else 0
        items.append({
            "text":        q.get("question_text", ""),
            "options":     opts,
            "correct":     ci,
            "explanation": q.get("solution", ""),
            "category":    "General",
        })

    js_q = json.dumps(items, ensure_ascii=False)

    # HTML placeholders
    out = out.replace("{{PAGE_TITLE}}",    f"{test_name} | GangLeader")
    out = out.replace("{{BADGE_TEXT}}",    "Mock Test")
    out = out.replace("{{EXAM_TITLE}}",    test_name)
    out = out.replace("{{EXAM_SUBTITLE}}", "Crack the Code. Lead the Gang.")
    out = out.replace("{{Q_COUNT}}",       str(total))
    out = out.replace("{{MINUTES}}",       str(mins))
    out = out.replace("{{MAX_MARKS}}",     str(total))
    out = out.replace("{{TOPBAR_NAME}}",   test_name)

    # JS placeholders  /*{{KEY}}*/default_value
    out = re.sub(r'/\*\{\{QUESTIONS\}\}\*/\[\]',
                 f'/*{{{{QUESTIONS}}}}*/{js_q}', out)
    out = re.sub(r'/\*\{\{PASSAGE\}\}\*/``',
                 '/*{{PASSAGE}}*/``', out)
    out = re.sub(r'/\*\{\{TITLE\}\}\*/"[^"]*"',
                 f'/*{{{{TITLE}}}}*/{json.dumps(test_name)}', out)
    out = re.sub(r'/\*\{\{POS\}\}\*/[\d.]+',     f'/*{{{{POS}}}}*/1',          out)
    out = re.sub(r'/\*\{\{NEG\}\}\*/[\d.]+',     f'/*{{{{NEG}}}}*/0.25',       out)
    out = re.sub(r'/\*\{\{TOTAL_SEC\}\}\*/[\d ]*\*[\d ]*',
                 f'/*{{{{TOTAL_SEC}}}}*/ {total_sec}', out)

    return out


# ── Sienova ───────────────────────────────────────────────────────────────────
def _sienova(questions, test_name, total, total_sec, mins):
    """
    Keep the HTML/CSS EXACTLY as the original file — only swap:
    1. <title>
    2. CFG object (title + mins)
    3. The Q = [...] data array
    4. Visible text: topic name, hdr-title, timer display, stats counts
    """
    out = _tpl("sienova_template.html")

    # Build Q array  { t, o, a, s }
    items = []
    for q in questions:
        opts = [o["text"] for o in q.get("options", [])]
        cl   = q.get("correct_answer", "A")
        ci   = LABELS.index(cl) if cl in LABELS else 0
        items.append({
            "t": q.get("question_text", ""),
            "o": opts,
            "a": ci,
            "s": q.get("solution", ""),
        })
    js_q = json.dumps(items, ensure_ascii=False)

    # 1. Page title
    out = re.sub(r'<title>[^<]*</title>',
                 f'<title>{test_name} | Sienova</title>', out)

    # 2. CFG object — replace title and mins only
    out = re.sub(
        r"const CFG\s*=\s*\{[^}]+\};",
        f"const CFG = {{ title: {json.dumps(test_name)}, mins: {mins}, pos: 1, neg: -0.25 }};",
        out
    )

    # 3. The Q data array — replace everything between [ and the closing ];
    #    The original has:  const Q = [\n  { ... },\n  ...\n];
    out = re.sub(
        r'(const Q\s*=\s*)\[[\s\S]*?\];',
        r'\g<1>' + js_q + ';',
        out
    )

    # 4. let secs — set to total_sec
    out = re.sub(
        r'let secs\s*=\s*CFG\.mins \* 60;',
        f'let secs = {total_sec};',
        out
    )

    # 5. Welcome card: topic name
    out = re.sub(
        r'(<div class="w-topic-name">)[^<]*(</div>)',
        rf'\g<1>{test_name}\g<2>',
        out
    )

    # 6. Welcome card: topic label
    out = re.sub(
        r'(<div class="w-topic-label">)[^<]*(</div>)',
        rf'\g<1>Mock Test\g<2>',
        out
    )

    # 7. Header title
    out = re.sub(
        r'(<div class="hdr-title" id="hdr-title">)[^<]*(</div>)',
        rf'\g<1>{test_name}\g<2>',
        out
    )

    # 8. Timer initial display
    out = re.sub(
        r'(<span class="timer-val" id="timer">)[^<]*(</span>)',
        rf'\g<1>{mins}:00\g<2>',
        out
    )

    # 9. Welcome stats: questions count
    out = re.sub(
        r'(<div class="w-stat"><span class="v">)(\d+)(</span><span class="l">Questions</span></div>)',
        rf'\g<1>{total}\g<3>',
        out
    )

    # 10. Welcome stats: minutes
    out = re.sub(
        r'(<div class="w-stat"><span class="v">)(\d+)(</span><span class="l">Minutes</span></div>)',
        rf'\g<1>{mins}\g<3>',
        out
    )

    # 11. q-label default text
    out = re.sub(
        r'(<div class="q-badge" id="q-label">)Q \d+ / \d+(</div>)',
        rf'\g<1>Q 1 / {total}\g<2>',
        out
    )

    # 12. Result modal: r-max and r-total
    out = re.sub(
        r'(out of <span id="r-max">)\d+(</span>)',
        rf'\g<1>{total}\g<2>',
        out
    )
    out = re.sub(
        r'(<span class="v" id="r-total">)\d+(</span>)',
        rf'\g<1>{total}\g<2>',
        out
    )

    return out
