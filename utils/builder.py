"""
HTML Builder
Uses the real GangLeader (template.html) and Sienova UI templates.
Templates are embedded as strings — no external file dependency at runtime.
"""

import json
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LABELS = ["A", "B", "C", "D", "E", "F"]

# Load templates once at import time from sibling template files if present,
# otherwise fall back to the embedded copies stored below.
_HERE = Path(__file__).parent


def _load_template(filename: str) -> str:
    p = _HERE / filename
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def build_html(quiz_data: dict, brand: str = "gangleader") -> str:
    questions  = quiz_data.get("questions", [])
    test_name  = quiz_data.get("test_name", "Quiz")
    total      = len(questions)
    total_sec  = 60 * 60   # 60 minutes
    mins       = total_sec // 60
    max_marks  = total

    if brand == "gangleader":
        return _build_gangleader(questions, test_name, total, total_sec, mins, max_marks)
    else:
        return _build_sienova(questions, test_name, total, total_sec, mins)


# ─────────────────────────────────────────────────────────────────────────────
# GangLeader — uses template.html with {{PLACEHOLDER}} substitution
# ─────────────────────────────────────────────────────────────────────────────

def _build_gangleader(questions, test_name, total, total_sec, mins, max_marks):
    tmpl = _load_template("gangleader_template.html")
    if not tmpl:
        raise FileNotFoundError(
            "gangleader_template.html not found in utils/. "
            "Place template.html there and rename it gangleader_template.html"
        )

    # Build QUESTIONS JS array
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
    js_questions = json.dumps(items, ensure_ascii=False)

    replacements = {
        "PAGE_TITLE":    f"{test_name} | GangLeader",
        "BADGE_TEXT":    "Mock Test",
        "EXAM_TITLE":    test_name,
        "EXAM_SUBTITLE": "Crack the Code. Lead the Gang.",
        "Q_COUNT":       str(total),
        "MINUTES":       str(mins),
        "MAX_MARKS":     str(max_marks),
        "TOPBAR_NAME":   test_name,
        "TITLE":         json.dumps(test_name),
        "POS":           "1",
        "NEG":           "0.25",
        "TOTAL_SEC":     str(total_sec),
        "PASSAGE":       "",
    }

    out = tmpl
    # Replace HTML placeholders: {{KEY}}
    for key, val in replacements.items():
        out = out.replace("{{" + key + "}}", val)

    # Replace JS placeholders: /*{{KEY}}*/value  or  /*{{KEY}}*/`...`
    out = re.sub(r'/\*\{\{QUESTIONS\}\}\*/\[\]',
                 f"/*{{{{QUESTIONS}}}}*/{js_questions}", out)
    out = re.sub(r'/\*\{\{PASSAGE\}\}\*/``',
                 '/*{{PASSAGE}}*/``', out)
    for key, val in replacements.items():
        # /*{{KEY}}*/anything  → /*{{KEY}}*/val
        out = re.sub(
            r'/\*\{\{' + re.escape(key) + r'\}\}\*/[^\n,;)]*',
            f'/*{{{{{key}}}}}*/{val}',
            out
        )

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Sienova — uses sienova template, strips dark mode, injects quiz data
# ─────────────────────────────────────────────────────────────────────────────

def _build_sienova(questions, test_name, total, total_sec, mins):
    tmpl = _load_template("sienova_template.html")
    if not tmpl:
        raise FileNotFoundError(
            "sienova_template.html not found in utils/. "
            "Place sienova_pipes_cistern_premium_v2.html there "
            "and rename it sienova_template.html"
        )

    # Build Q JS array  { t, o, a, s }
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

    out = tmpl

    # 1. Strip the entire dark-mode :root block and replace with light-only tokens
    #    (remove the dark :root { ... } and the html[data-theme="light"] { ... } wrapper
    #     then replace :root with the light values)
    out = _promote_light_theme(out)

    # 2. Remove theme toggle button from HTML (no dark mode UI needed)
    out = re.sub(r'<!-- Theme Toggle -->.*?</button>', '', out, flags=re.DOTALL)
    out = re.sub(r'<button class="theme-btn"[^>]*>.*?</button>', '', out, flags=re.DOTALL)

    # 3. Replace page title
    out = re.sub(r'<title>[^<]*</title>', f'<title>{test_name} | Sienova</title>', out)

    # 4. Replace the hardcoded CFG title and mins
    out = re.sub(
        r"const CFG\s*=\s*\{[^}]*\};",
        f"const CFG = {{ title: {json.dumps(test_name)}, mins: {mins}, pos: 1, neg: -0.25 }};",
        out
    )

    # 5. Replace the Q array
    out = re.sub(r'const Q\s*=\s*\[[\s\S]*?\];\s*\n', f'const Q = {js_q};\n', out)

    # 6. Replace topic name in welcome card
    out = re.sub(
        r'<div class="w-topic-name">[^<]*</div>',
        f'<div class="w-topic-name">{test_name}</div>',
        out
    )

    # 7. Replace hdr-title
    out = re.sub(
        r'<div class="hdr-title" id="hdr-title">[^<]*</div>',
        f'<div class="hdr-title" id="hdr-title">{test_name}</div>',
        out
    )

    # 8. Replace timer initial display
    out = re.sub(
        r'<span class="timer-val" id="timer">[^<]*</span>',
        f'<span class="timer-val" id="timer">{mins}:00</span>',
        out
    )

    # 9. Update total questions stats in welcome card
    out = re.sub(
        r'(<div class="w-stat"><span class="v">)\d+(</span><span class="l">Questions</span></div>)',
        rf'\g<1>{total}\2',
        out
    )
    out = re.sub(
        r'(<div class="w-stat"><span class="v">)\d+(</span><span class="l">Minutes</span></div>)',
        rf'\g<1>{mins}\2',
        out
    )

    # 10. Update result modal total
    out = re.sub(
        r'(<div class="res-sub">out of <span id="r-max">)\d+(</span> marks</div>)',
        rf'\g<1>{total}\2',
        out
    )
    out = re.sub(
        r'(<div class="res-cell"><span class="v" id="r-total">)\d+(</span>)',
        rf'\g<1>{total}\2',
        out
    )

    # 11. Update q-label default text
    out = re.sub(
        r'<div class="q-badge" id="q-label">Q \d+ / \d+</div>',
        f'<div class="q-badge" id="q-label">Q 1 / {total}</div>',
        out
    )

    # 12. Remove secs = CFG.mins * 60 line (secs already declared above)
    #     and update it to use total_sec
    out = re.sub(
        r'let secs\s*=\s*CFG\.mins \* 60;',
        f'let secs = {total_sec};',
        out
    )

    return out


def _promote_light_theme(html: str) -> str:
    """
    1. Replace the dark-mode :root { ... } block with the light-mode token values.
    2. Remove the html[data-theme="light"] { ... } override block entirely.
    3. Remove all other html[data-theme="light"] selector blocks.
    4. Remove theme toggle JS function and saved-theme logic.
    """
    # Step 1: Replace dark :root with light token values
    light_root = """:root {
  --ink:     #f5f4f0;
  --ink2:    #ffffff;
  --ink3:    #ede9e0;
  --ink4:    #d8d3c8;
  --glass:   rgba(0,0,0,0.03);
  --glass2:  rgba(0,0,0,0.06);
  --line:    rgba(0,0,0,0.08);
  --line2:   rgba(0,0,0,0.14);
  --gold:    #b8860b;
  --gold2:   #d4a017;
  --gold3:   rgba(184,134,11,0.15);
  --goldg:   linear-gradient(135deg,#c9952e,#e8b84b,#b8860b);
  --cream:   #1a1710;
  --snow:    #2c2a22;
  --fog:     #6b6755;
  --fog2:    #9b9784;
  --ok:      #1a9970;
  --err:     #d63c3c;
  --warn:    #c47d00;
  --r:       12px;
  --t:       0.2s cubic-bezier(0.4,0,0.2,1);
  --shadow:  0 24px 64px rgba(0,0,0,0.12);
  --glow:    0 0 40px rgba(184,134,11,0.10);

  --pal-ans-bg:  #d4f5e9; --pal-ans-bd:  #52c49a; --pal-ans-tx:  #0d6e4a;
  --pal-skip-bg: #fde8e8; --pal-skip-bd: #e07070; --pal-skip-tx: #9b2020;
  --pal-mrk-bg:  #fff3d0; --pal-mrk-bd:  #d4920a; --pal-mrk-tx:  #7a4f00;
  --pal-mrka-bg: #fef0c0; --pal-mrka-bd: #c9952e; --pal-mrka-tx: #6b4000;
  --pal-cur-bg:  #fff8e6; --pal-cur-bd:  #b8860b; --pal-cur-tx:  #6b4a00;
  --pal-sa-bg:   #c8f5e5; --pal-sa-bd:   #3aae84; --pal-sa-tx:   #0a5c38;
  --pal-sw-bg:   #fce0e0; --pal-sw-bd:   #d05050; --pal-sw-tx:   #8a1515;
  --pal-ss-bg:   #f0ede8; --pal-ss-bd:   #ccc9c0; --pal-ss-tx:   #8a8470;
}"""

    # Remove old dark :root block
    html = re.sub(
        r'/\* ══+\s*THEME TOKENS[^*]*\*/ *\n:root \{[^}]*(?:\{[^}]*\}[^}]*)?\}',
        light_root,
        html,
        count=1,
        flags=re.DOTALL
    )

    # Remove the light theme comment + html[data-theme="light"] { ... } block
    html = re.sub(
        r'/\* ══+\s*LIGHT THEME[^*]*\*/\s*html\[data-theme="light"\]\s*\{[^}]*\}',
        '',
        html,
        flags=re.DOTALL
    )

    # Remove ALL remaining html[data-theme="light"] ... { } blocks
    html = re.sub(
        r'html\[data-theme="light"\][^\{]*\{[^}]*\}',
        '',
        html,
        flags=re.DOTALL
    )

    # Remove theme toggle CSS block
    html = re.sub(
        r'/\* ══+\s*THEME TOGGLE[^*]*\*/.*?(?=/\* ══)',
        '',
        html,
        flags=re.DOTALL
    )

    # Remove toggleTheme JS function
    html = re.sub(r'function toggleTheme\(\)[^}]*\}', '', html, flags=re.DOTALL)

    # Remove saved-theme IIFE
    html = re.sub(r'\(function\(\)[^}]*sienova-theme[^}]*\}\)\(\);', '', html, flags=re.DOTALL)

    return html
