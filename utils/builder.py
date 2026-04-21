"""
HTML Builder
Generates full, self-contained quiz HTML files in GangLeader or Sienova branding.
"""

import json
import logging
from config import GANGLEADER_BRAND, SIENOVA_BRAND

logger = logging.getLogger(__name__)


def build_html(quiz_data: dict, brand: str = "gangleader") -> str:
    """
    Build a complete self-contained quiz HTML from quiz_data dict.
    brand: "gangleader" | "sienova"
    """
    b = GANGLEADER_BRAND if brand == "gangleader" else SIENOVA_BRAND
    questions = quiz_data.get("questions", [])
    test_name = quiz_data.get("test_name", "Quiz")
    total = len(questions)

    js_data = json.dumps(questions, ensure_ascii=False)

    if brand == "gangleader":
        return _gangleader_template(b, test_name, total, js_data)
    else:
        return _sienova_template(b, test_name, total, js_data)


# ─────────────────────────────────────────────────────────────────────────────
# GangLeader Template
# ─────────────────────────────────────────────────────────────────────────────
def _gangleader_template(b: dict, test_name: str, total: int, js_data: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{test_name} | {b['name']}</title>
<style>
  /* ── Reset & Base ── */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --gold:       {b['primary']};
    --gold-dark:  {b['primary_dark']};
    --gold-light: #F0D080;
    --gold-glow:  rgba(212,168,67,0.18);
    --bg:         {b['bg']};
    --surface:    {b['surface']};
    --text:       {b['text']};
    --text-muted: #6B6B6B;
    --border:     rgba(212,168,67,0.25);
    --radius:     14px;
    --shadow:     0 4px 24px rgba(0,0,0,0.08);
    --shadow-lg:  0 8px 40px rgba(0,0,0,0.12);
    --transition: 0.22s cubic-bezier(.4,0,.2,1);
  }}
  html {{ scroll-behavior: smooth; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
  }}

  /* ── Layout ── */
  #app {{ display: flex; flex-direction: column; min-height: 100vh; }}

  /* ── Top Nav ── */
  .top-nav {{
    position: sticky; top: 0; z-index: 100;
    background: var(--surface);
    border-bottom: 2px solid var(--gold);
    padding: 0 20px;
    display: flex; align-items: center; justify-content: space-between;
    height: 56px;
    box-shadow: 0 2px 12px rgba(212,168,67,0.10);
  }}
  .nav-brand {{
    display: flex; align-items: center; gap: 10px;
    font-size: 1.15rem; font-weight: 800;
    letter-spacing: -0.02em; color: var(--gold-dark);
  }}
  .nav-brand .logo {{ font-size: 1.4rem; }}
  .nav-meta {{ font-size: 0.78rem; color: var(--text-muted); text-align: right; }}
  .nav-meta strong {{ color: var(--text); }}
  .timer-badge {{
    background: var(--gold);
    color: #fff;
    font-weight: 700;
    font-size: 0.85rem;
    padding: 4px 14px;
    border-radius: 999px;
    letter-spacing: 0.04em;
    min-width: 80px;
    text-align: center;
  }}
  .timer-badge.warning {{ background: #E53E3E; animation: pulse 1s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.7}} }}

  /* ── Main Content ── */
  .main-wrap {{
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 260px;
    gap: 20px;
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 20px;
    width: 100%;
  }}
  @media(max-width:760px){{
    .main-wrap{{ grid-template-columns:1fr; }}
    .sidebar{{ order:-1; }}
  }}

  /* ── Question Area ── */
  .question-area {{
    display: flex; flex-direction: column; gap: 20px;
  }}
  .q-header {{
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 8px;
  }}
  .q-num {{
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--text-muted);
  }}
  .q-marks {{
    font-size: 0.75rem; background: var(--gold-glow);
    color: var(--gold-dark); border: 1px solid var(--border);
    padding: 3px 12px; border-radius: 999px; font-weight: 600;
  }}
  .q-card {{
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: var(--radius);
    padding: 26px 28px;
    box-shadow: var(--shadow);
    transition: box-shadow var(--transition);
  }}
  .q-card:hover {{ box-shadow: var(--shadow-lg); }}
  .q-text {{
    font-size: 1.05rem; font-weight: 500; line-height: 1.7;
    margin-bottom: 24px; color: var(--text);
  }}

  /* ── Options ── */
  .options-grid {{
    display: flex; flex-direction: column; gap: 12px;
  }}
  .option-btn {{
    display: flex; align-items: center; gap: 14px;
    background: var(--bg);
    border: 1.5px solid var(--border);
    border-radius: 10px;
    padding: 13px 16px;
    cursor: pointer;
    transition: all var(--transition);
    text-align: left; width: 100%;
    font-size: 0.95rem; color: var(--text);
    position: relative; overflow: hidden;
  }}
  .option-btn::before {{
    content: ''; position: absolute; inset: 0;
    background: var(--gold-glow); opacity: 0;
    transition: opacity var(--transition);
  }}
  .option-btn:hover::before {{ opacity: 1; }}
  .option-btn:hover {{ border-color: var(--gold); transform: translateX(3px); }}
  .opt-label {{
    width: 32px; height: 32px; flex-shrink: 0;
    border-radius: 50%;
    background: var(--bg);
    border: 2px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.85rem; color: var(--text-muted);
    transition: all var(--transition);
  }}
  .opt-text {{ flex: 1; line-height: 1.5; }}

  /* State: selected */
  .option-btn.selected {{ border-color: var(--gold); background: rgba(212,168,67,0.07); }}
  .option-btn.selected .opt-label {{
    background: var(--gold); border-color: var(--gold); color: #fff;
  }}
  /* State: correct */
  .option-btn.correct {{ border-color: #22C55E; background: rgba(34,197,94,0.07); }}
  .option-btn.correct .opt-label {{ background: #22C55E; border-color: #22C55E; color: #fff; }}
  /* State: wrong */
  .option-btn.wrong {{ border-color: #EF4444; background: rgba(239,68,68,0.06); }}
  .option-btn.wrong .opt-label {{ background: #EF4444; border-color: #EF4444; color: #fff; }}

  /* ── Solution ── */
  .solution-box {{
    margin-top: 18px;
    background: linear-gradient(135deg, rgba(212,168,67,0.06), rgba(212,168,67,0.02));
    border: 1.5px solid rgba(212,168,67,0.30);
    border-radius: 10px;
    padding: 16px 18px;
    display: none;
  }}
  .solution-box.visible {{ display: block; animation: fadeIn .3s ease; }}
  .solution-label {{
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--gold-dark);
    margin-bottom: 8px; display: flex; align-items: center; gap: 6px;
  }}
  .solution-text {{ font-size: 0.93rem; color: var(--text); line-height: 1.65; }}
  @keyframes fadeIn {{ from{{opacity:0;transform:translateY(6px)}} to{{opacity:1;transform:none}} }}

  /* ── Nav Buttons ── */
  .q-nav {{
    display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  }}
  .btn {{
    padding: 10px 22px; border-radius: 999px; border: none;
    font-weight: 700; font-size: 0.88rem; cursor: pointer;
    transition: all var(--transition); letter-spacing: 0.02em;
  }}
  .btn-primary {{
    background: linear-gradient(135deg, var(--gold), var(--gold-dark));
    color: #fff;
    box-shadow: 0 4px 14px rgba(212,168,67,0.35);
  }}
  .btn-primary:hover {{ transform:translateY(-1px); box-shadow:0 6px 20px rgba(212,168,67,0.45); }}
  .btn-secondary {{
    background: var(--surface); color: var(--text);
    border: 1.5px solid var(--border);
  }}
  .btn-secondary:hover {{ border-color: var(--gold); background: var(--gold-glow); }}
  .btn-danger {{
    background: #EF4444; color: #fff;
    box-shadow: 0 4px 14px rgba(239,68,68,0.25);
  }}
  .btn-danger:hover {{ background: #DC2626; }}
  .btn:disabled {{ opacity:.45; cursor:not-allowed; transform:none!important; }}

  /* ── Sidebar ── */
  .sidebar {{
    display: flex; flex-direction: column; gap: 16px;
  }}
  .sidebar-card {{
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: var(--radius);
    padding: 18px;
    box-shadow: var(--shadow);
  }}
  .sidebar-title {{
    font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 14px;
    display: flex; align-items: center; gap: 6px;
  }}

  /* ── Palette ── */
  .palette-grid {{
    display: grid; grid-template-columns: repeat(5,1fr); gap: 7px;
  }}
  .p-btn {{
    aspect-ratio: 1; border-radius: 8px; border: 1.5px solid var(--border);
    font-size: 0.78rem; font-weight: 700; cursor: pointer;
    transition: all var(--transition);
    background: var(--bg); color: var(--text-muted);
  }}
  .p-btn:hover {{ border-color: var(--gold); color: var(--gold-dark); }}
  .p-btn.active {{ border-color: var(--gold); box-shadow: 0 0 0 2px var(--gold); }}
  /* States */
  .p-btn.answered   {{ background: var(--gold); color: #fff; border-color: var(--gold); }}
  .p-btn.skipped    {{ background: #FB923C; color: #fff; border-color: #FB923C; }}
  .p-btn.marked     {{ background: #A855F7; color: #fff; border-color: #A855F7; }}
  .p-btn.marked-ans {{ background: #6366F1; color: #fff; border-color: #6366F1; }}
  .p-btn.current    {{ border-color: var(--gold); box-shadow: 0 0 0 3px rgba(212,168,67,.4); }}

  /* ── Legend ── */
  .legend {{ display: flex; flex-direction: column; gap: 8px; }}
  .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 0.80rem; }}
  .legend-dot {{
    width: 14px; height: 14px; border-radius: 4px; flex-shrink: 0;
  }}

  /* ── Stats ── */
  .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  .stat-item {{ text-align: center; }}
  .stat-num {{
    font-size: 1.6rem; font-weight: 800; color: var(--gold-dark); line-height: 1;
  }}
  .stat-lbl {{ font-size: 0.7rem; color: var(--text-muted); margin-top: 3px; }}

  /* ── Score Screen ── */
  #score-screen {{
    display: none; flex-direction: column; align-items: center;
    justify-content: center; min-height: 80vh;
    padding: 40px 20px; text-align: center;
  }}
  #score-screen.visible {{ display: flex; }}
  .score-trophy {{ font-size: 5rem; margin-bottom: 16px; }}
  .score-headline {{
    font-size: 2rem; font-weight: 900; color: var(--gold-dark);
    letter-spacing: -0.03em; margin-bottom: 6px;
  }}
  .score-sub {{ font-size: 1rem; color: var(--text-muted); margin-bottom: 32px; }}
  .score-grid {{
    display: grid; grid-template-columns: repeat(auto-fit,minmax(130px,1fr));
    gap: 16px; max-width: 600px; width: 100%; margin-bottom: 32px;
  }}
  .score-card {{
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 16px;
    box-shadow: var(--shadow);
  }}
  .score-card .val {{ font-size: 2rem; font-weight: 900; }}
  .score-card .lbl {{ font-size: 0.75rem; color: var(--text-muted); margin-top: 4px; }}
  .score-card.gold .val {{ color: var(--gold-dark); }}
  .score-card.green .val {{ color: #22C55E; }}
  .score-card.red .val {{ color: #EF4444; }}
  .score-card.blue .val {{ color: #3B82F6; }}

  .mark-indicator {{
    position: absolute; top: 8px; right: 8px;
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.05em;
    padding: 2px 8px; border-radius: 999px;
    pointer-events: none;
  }}
  .mark-indicator.marked {{ background: #F3E8FF; color: #9333EA; }}

  /* ── Utility ── */
  .flex-gap {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
  .mt-auto {{ margin-top: auto; }}
  select {{
    padding: 7px 12px; border-radius: 8px;
    border: 1.5px solid var(--border);
    background: var(--surface); color: var(--text);
    font-size: 0.88rem; font-weight: 600; cursor: pointer;
    outline: none;
  }}
  select:focus {{ border-color: var(--gold); }}

  /* ── Header strip ── */
  .brand-strip {{
    background: linear-gradient(135deg, var(--gold-dark) 0%, var(--gold) 60%, #F0D080 100%);
    color: #fff; text-align: center;
    padding: 14px 20px 12px;
  }}
  .brand-strip h1 {{
    font-size: 1.1rem; font-weight: 900; letter-spacing: -0.01em;
  }}
  .brand-strip p {{ font-size: 0.78rem; opacity: .85; margin-top: 2px; }}

  /* Scrollbar */
  ::-webkit-scrollbar {{ width: 5px; }}
  ::-webkit-scrollbar-track {{ background: transparent; }}
  ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 99px; }}
</style>
</head>
<body>
<div id="app">

  <!-- Brand Strip -->
  <div class="brand-strip">
    <h1>{b['logo_emoji']} {b['name']} — {test_name}</h1>
    <p>{b['tagline']}</p>
  </div>

  <!-- Top Nav -->
  <nav class="top-nav">
    <div class="nav-brand">
      <span class="logo">{b['logo_emoji']}</span>
      <span>{b['name']}</span>
    </div>
    <span id="timer" class="timer-badge">60:00</span>
    <div class="nav-meta">
      <strong id="nav-qnum">Q1</strong> of <strong>{total}</strong>
    </div>
  </nav>

  <!-- Main Quiz Layout -->
  <div id="quiz-wrap">
    <div class="main-wrap">

      <!-- Question Area -->
      <div class="question-area">
        <div class="q-header">
          <span class="q-num" id="q-num-label">Question 1 of {total}</span>
          <span class="q-marks" id="q-marks-label">1 Mark</span>
        </div>

        <div class="q-card" id="q-card">
          <p class="q-text" id="q-text">Loading...</p>
          <div class="options-grid" id="options-grid"></div>
          <div class="solution-box" id="solution-box">
            <div class="solution-label">💡 Solution</div>
            <div class="solution-text" id="solution-text"></div>
          </div>
        </div>

        <!-- Navigation Buttons -->
        <div class="q-nav">
          <button class="btn btn-secondary" id="btn-prev" onclick="prevQ()">← Prev</button>
          <button class="btn btn-secondary" id="btn-next" onclick="nextQ()">Next →</button>
          <button class="btn btn-secondary" onclick="markForReview()">🔖 Mark</button>
          <button class="btn btn-secondary" onclick="clearResponse()">Clear</button>
          <div style="margin-left:auto">
            <button class="btn btn-danger" onclick="confirmSubmit()">Submit Test</button>
          </div>
        </div>
      </div>

      <!-- Sidebar -->
      <div class="sidebar">

        <!-- Stats -->
        <div class="sidebar-card">
          <div class="sidebar-title">📊 Progress</div>
          <div class="stats-grid">
            <div class="stat-item"><div class="stat-num" id="s-answered">0</div><div class="stat-lbl">Answered</div></div>
            <div class="stat-item"><div class="stat-num" id="s-skipped">0</div><div class="stat-lbl">Skipped</div></div>
            <div class="stat-item"><div class="stat-num" id="s-marked">0</div><div class="stat-lbl">Marked</div></div>
            <div class="stat-item"><div class="stat-num" id="s-not-visited">0</div><div class="stat-lbl">Not Visited</div></div>
          </div>
        </div>

        <!-- Question Palette -->
        <div class="sidebar-card">
          <div class="sidebar-title">📋 Question Palette</div>
          <div class="palette-grid" id="palette"></div>
        </div>

        <!-- Legend -->
        <div class="sidebar-card">
          <div class="sidebar-title">🔑 Legend</div>
          <div class="legend">
            <div class="legend-item"><div class="legend-dot" style="background:var(--gold)"></div> Answered</div>
            <div class="legend-item"><div class="legend-dot" style="background:#FB923C"></div> Skipped / Not Answered</div>
            <div class="legend-item"><div class="legend-dot" style="background:#A855F7"></div> Marked for Review</div>
            <div class="legend-item"><div class="legend-dot" style="background:#6366F1"></div> Marked + Answered</div>
            <div class="legend-item"><div class="legend-dot" style="background:var(--bg);border:1.5px solid var(--border)"></div> Not Visited</div>
          </div>
        </div>

      </div>
    </div>
  </div>

  <!-- Score Screen (hidden until submit) -->
  <div id="score-screen">
    <div class="score-trophy">🏆</div>
    <div class="score-headline" id="score-grade">Excellent!</div>
    <div class="score-sub" id="score-sub">Test completed</div>
    <div class="score-grid">
      <div class="score-card gold"><div class="val" id="sc-score">0</div><div class="lbl">Score</div></div>
      <div class="score-card green"><div class="val" id="sc-correct">0</div><div class="lbl">Correct</div></div>
      <div class="score-card red"><div class="val" id="sc-wrong">0</div><div class="lbl">Wrong</div></div>
      <div class="score-card blue"><div class="val" id="sc-unattempted">0</div><div class="lbl">Unattempted</div></div>
    </div>
    <div class="flex-gap">
      <button class="btn btn-primary" onclick="reviewAnswers()">📖 Review Answers</button>
      <button class="btn btn-secondary" onclick="restartQuiz()">🔄 Restart</button>
    </div>
  </div>

</div><!-- #app -->

<script>
// ── Data ──────────────────────────────────────────────────────────────────────
const quizData = {js_data};

// ── State ─────────────────────────────────────────────────────────────────────
let current = 0;
let submitted = false;
// q states: 0=not-visited, 1=answered, 2=skipped, 3=marked, 4=marked+answered
const qState  = new Array(quizData.length).fill(0);
const answers = new Array(quizData.length).fill(null);
let timerSecs = 60 * 60; // 60 min
let timerInterval;

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {{
  buildPalette();
  renderQ(0);
  startTimer();
}}

// ── Timer ─────────────────────────────────────────────────────────────────────
function startTimer() {{
  timerInterval = setInterval(() => {{
    timerSecs--;
    if (timerSecs <= 0) {{ clearInterval(timerInterval); submitQuiz(); return; }}
    const m = String(Math.floor(timerSecs/60)).padStart(2,'0');
    const s = String(timerSecs%60).padStart(2,'0');
    const el = document.getElementById('timer');
    el.textContent = m+':'+s;
    if (timerSecs <= 300) el.classList.add('warning');
  }}, 1000);
}}

// ── Palette ───────────────────────────────────────────────────────────────────
function buildPalette() {{
  const grid = document.getElementById('palette');
  grid.innerHTML = '';
  quizData.forEach((_, i) => {{
    const b = document.createElement('button');
    b.className = 'p-btn';
    b.textContent = i+1;
    b.onclick = () => goToQ(i);
    b.id = 'p-'+i;
    grid.appendChild(b);
  }});
  refreshPalette();
}}

function refreshPalette() {{
  quizData.forEach((_, i) => {{
    const b = document.getElementById('p-'+i);
    if (!b) return;
    b.className = 'p-btn';
    const s = qState[i];
    if      (s === 0) b.classList.add('unvisited');
    else if (s === 1) b.classList.add('answered');
    else if (s === 2) b.classList.add('skipped');
    else if (s === 3) b.classList.add('marked');
    else if (s === 4) b.classList.add('marked-ans');
    if (i === current) b.classList.add('current', 'active');
  }});
  updateStats();
}}

// ── Render Question ───────────────────────────────────────────────────────────
function renderQ(idx) {{
  const q = quizData[idx];
  if (!q) return;
  current = idx;

  if (qState[idx] === 0) qState[idx] = submitted ? 2 : 2; // mark as skipped until answered

  document.getElementById('q-num-label').textContent = `Question ${{idx+1}} of ${{quizData.length}}`;
  document.getElementById('q-marks-label').textContent = `${{q.marks || 1}} Mark${{q.marks !== 1 ? 's' : ''}}`;
  document.getElementById('nav-qnum').textContent = `Q${{idx+1}}`;
  document.getElementById('q-text').textContent = q.question_text || 'No question text.';

  // Options
  const grid = document.getElementById('options-grid');
  grid.innerHTML = '';
  (q.options || []).forEach((opt, oi) => {{
    const btn = document.createElement('button');
    btn.className = 'option-btn';
    btn.innerHTML = `<span class="opt-label">${{opt.label}}</span><span class="opt-text">${{opt.text}}</span>`;
    btn.dataset.label = opt.label;
    if (submitted) {{
      if (opt.label === q.correct_answer) btn.classList.add('correct');
      else if (answers[idx] === opt.label) btn.classList.add('wrong');
      btn.disabled = true;
    }} else {{
      if (answers[idx] === opt.label) btn.classList.add('selected');
      btn.onclick = () => selectOption(idx, opt.label);
    }}
    grid.appendChild(btn);
  }});

  // Solution
  const solBox = document.getElementById('solution-box');
  const solText = document.getElementById('solution-text');
  if (submitted && q.solution) {{
    solText.textContent = q.solution;
    solBox.classList.add('visible');
  }} else {{
    solBox.classList.remove('visible');
  }}

  // Nav buttons
  document.getElementById('btn-prev').disabled = idx === 0;
  document.getElementById('btn-next').disabled = idx === quizData.length - 1;

  refreshPalette();
}}

function selectOption(qIdx, label) {{
  if (submitted) return;
  answers[qIdx] = label;
  qState[qIdx] = qState[qIdx] === 3 ? 4 : 1; // marked+answered or answered
  renderQ(qIdx);
}}

// ── Navigation ────────────────────────────────────────────────────────────────
function goToQ(idx) {{ renderQ(idx); }}
function prevQ() {{ if (current > 0) renderQ(current - 1); }}
function nextQ() {{
  if (qState[current] === 0 || qState[current] === 2) qState[current] = 2; // skipped
  if (current < quizData.length - 1) renderQ(current + 1);
}}

function markForReview() {{
  qState[current] = answers[current] ? 4 : 3;
  refreshPalette();
}}

function clearResponse() {{
  answers[current] = null;
  qState[current] = 2; // skipped
  renderQ(current);
}}

// ── Submit ────────────────────────────────────────────────────────────────────
function confirmSubmit() {{
  const unanswered = answers.filter(a => !a).length;
  const msg = unanswered > 0
    ? `You have ${{unanswered}} unanswered question(s). Submit anyway?`
    : 'Are you sure you want to submit the test?';
  if (confirm(msg)) submitQuiz();
}}

function submitQuiz() {{
  clearInterval(timerInterval);
  submitted = true;

  let correct = 0, wrong = 0, unattempted = 0;
  quizData.forEach((q, i) => {{
    if (!answers[i]) unattempted++;
    else if (answers[i] === q.correct_answer) correct++;
    else wrong++;
  }});
  const score = correct * 1 - wrong * 0.25;

  // Show score screen
  document.getElementById('quiz-wrap').style.display = 'none';
  const ss = document.getElementById('score-screen');
  ss.classList.add('visible');

  document.getElementById('sc-score').textContent = score.toFixed(2);
  document.getElementById('sc-correct').textContent = correct;
  document.getElementById('sc-wrong').textContent = wrong;
  document.getElementById('sc-unattempted').textContent = unattempted;

  const pct = (correct / quizData.length) * 100;
  const [grade, sub] = pct >= 90 ? ['Outstanding! 🌟', 'You nailed it!']
    : pct >= 75 ? ['Excellent! 🏆', 'Great performance!']
    : pct >= 60 ? ['Good Job! 👍', 'Keep improving!']
    : pct >= 40 ? ['Keep Trying! 💪', 'Practice makes perfect.']
    : ['Needs Work 📚', 'Review your concepts.'];
  document.getElementById('score-grade').textContent = grade;
  document.getElementById('score-sub').textContent = `${{sub}} (${{pct.toFixed(1)}}%)`;
}}

function reviewAnswers() {{
  document.getElementById('score-screen').classList.remove('visible');
  document.getElementById('quiz-wrap').style.display = '';
  renderQ(0);
}}

function restartQuiz() {{
  location.reload();
}}

function updateStats() {{
  const ans = qState.filter(s => s===1||s===4).length;
  const skp = qState.filter(s => s===2).length;
  const mrk = qState.filter(s => s===3||s===4).length;
  const nv  = qState.filter(s => s===0).length;
  document.getElementById('s-answered').textContent   = ans;
  document.getElementById('s-skipped').textContent    = skp;
  document.getElementById('s-marked').textContent     = mrk;
  document.getElementById('s-not-visited').textContent = nv;
}}

init();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Sienova Template
# ─────────────────────────────────────────────────────────────────────────────
def _sienova_template(b: dict, test_name: str, total: int, js_data: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{test_name} | {b['name']}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --blue:       {b['primary']};
    --blue-dark:  {b['primary_dark']};
    --blue-light: #DBEAFE;
    --blue-glow:  rgba(37,99,235,0.10);
    --bg:         {b['bg']};
    --surface:    {b['surface']};
    --text:       {b['text']};
    --text-muted: #64748B;
    --border:     #E2E8F0;
    --radius:     12px;
    --shadow:     0 2px 16px rgba(15,23,42,0.07);
    --shadow-lg:  0 8px 32px rgba(15,23,42,0.12);
    --transition: 0.20s cubic-bezier(.4,0,.2,1);
  }}
  html {{ scroll-behavior: smooth; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
  }}
  #app {{ display: flex; flex-direction: column; min-height: 100vh; }}

  /* ── Header ── */
  .sienova-header {{
    background: linear-gradient(135deg, var(--blue-dark) 0%, var(--blue) 100%);
    color: #fff; padding: 0 24px;
    display: flex; align-items: center; justify-content: space-between;
    height: 58px;
    box-shadow: 0 2px 16px rgba(37,99,235,0.25);
    position: sticky; top: 0; z-index: 100;
  }}
  .sh-brand {{ display:flex; align-items:center; gap:10px; font-weight:800; font-size:1.05rem; }}
  .sh-brand .logo {{ font-size: 1.3rem; }}
  .sh-right {{ display:flex; align-items:center; gap:16px; }}
  .timer-pill {{
    background: rgba(255,255,255,0.18);
    backdrop-filter: blur(4px);
    border: 1px solid rgba(255,255,255,0.3);
    color: #fff; font-weight: 700;
    padding: 5px 16px; border-radius: 999px;
    font-size: 0.88rem; letter-spacing: 0.04em;
    min-width: 84px; text-align: center;
  }}
  .timer-pill.warning {{ background: rgba(239,68,68,0.85); animation: pulse 1s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.7}} }}
  .q-counter {{ font-size: 0.82rem; opacity: .85; }}

  /* ── Layout ── */
  .sv-wrap {{
    flex: 1; display: grid;
    grid-template-columns: 1fr 250px;
    gap: 20px; max-width: 1080px;
    margin: 0 auto; padding: 22px 18px; width: 100%;
  }}
  @media(max-width:740px){{
    .sv-wrap{{ grid-template-columns:1fr; }}
    .sv-sidebar{{ order:-1; }}
  }}

  /* ── Question Card ── */
  .q-section {{ display:flex; flex-direction:column; gap:16px; }}
  .q-meta {{ display:flex; align-items:center; justify-content:space-between; }}
  .q-badge {{
    font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:.07em;
    color: var(--blue); background: var(--blue-light); padding: 4px 12px; border-radius:999px;
  }}
  .marks-tag {{
    font-size:0.75rem; color:var(--text-muted);
    background:var(--bg); border:1px solid var(--border); padding:3px 12px; border-radius:999px;
  }}
  .q-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px 26px;
    box-shadow: var(--shadow);
    transition: box-shadow var(--transition);
  }}
  .q-card:hover {{ box-shadow: var(--shadow-lg); }}
  .q-text {{ font-size:1rem; font-weight:500; line-height:1.75; margin-bottom:22px; }}

  /* ── Options ── */
  .opts {{ display:flex; flex-direction:column; gap:10px; }}
  .opt {{
    display:flex; align-items:center; gap:12px;
    border: 1px solid var(--border);
    border-radius: 9px; padding:12px 15px;
    cursor:pointer; transition: all var(--transition);
    background: var(--bg); width:100%; text-align:left; font-size:0.94rem;
  }}
  .opt:hover {{ border-color:var(--blue); background:var(--blue-glow); transform:translateX(2px); }}
  .opt-lbl {{
    width:30px; height:30px; flex-shrink:0;
    border-radius:50%; border:1.5px solid var(--border);
    display:flex; align-items:center; justify-content:center;
    font-weight:700; font-size:0.82rem; color:var(--text-muted);
    transition: all var(--transition);
  }}
  .opt-txt {{ flex:1; line-height:1.5; }}
  .opt.selected {{ border-color:var(--blue); background:var(--blue-glow); }}
  .opt.selected .opt-lbl {{ background:var(--blue); border-color:var(--blue); color:#fff; }}
  .opt.correct {{ border-color:#16A34A; background:rgba(22,163,74,.07); }}
  .opt.correct .opt-lbl {{ background:#16A34A; border-color:#16A34A; color:#fff; }}
  .opt.wrong {{ border-color:#DC2626; background:rgba(220,38,38,.06); }}
  .opt.wrong .opt-lbl {{ background:#DC2626; border-color:#DC2626; color:#fff; }}

  /* ── Solution ── */
  .sv-solution {{
    margin-top:14px; padding:15px 18px;
    background: linear-gradient(135deg,rgba(37,99,235,.05),rgba(37,99,235,.02));
    border:1px solid rgba(37,99,235,.2); border-radius:9px; display:none;
  }}
  .sv-solution.show {{ display:block; animation:fadeIn .3s ease; }}
  .sv-sol-lbl {{ font-size:.72rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--blue); margin-bottom:8px; }}
  .sv-sol-text {{ font-size:.92rem; line-height:1.65; }}
  @keyframes fadeIn {{ from{{opacity:0;transform:translateY(5px)}} to{{opacity:1;transform:none}} }}

  /* ── Buttons ── */
  .q-actions {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
  .btn {{ padding:9px 20px; border-radius:8px; border:none; font-weight:700;
    font-size:.86rem; cursor:pointer; transition:all var(--transition); }}
  .btn-blue {{ background:var(--blue); color:#fff; box-shadow:0 3px 12px rgba(37,99,235,.3); }}
  .btn-blue:hover {{ background:var(--blue-dark); transform:translateY(-1px); }}
  .btn-outline {{ background:var(--surface); color:var(--text); border:1px solid var(--border); }}
  .btn-outline:hover {{ border-color:var(--blue); background:var(--blue-glow); }}
  .btn-red {{ background:#DC2626; color:#fff; }}
  .btn-red:hover {{ background:#B91C1C; }}
  .btn:disabled {{ opacity:.45; cursor:not-allowed; transform:none!important; }}
  .btn-ml-auto {{ margin-left:auto; }}

  /* ── Sidebar ── */
  .sv-sidebar {{ display:flex; flex-direction:column; gap:14px; }}
  .sv-card {{
    background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); padding:16px; box-shadow:var(--shadow);
  }}
  .sv-card-title {{
    font-size:.73rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em;
    color:var(--text-muted); margin-bottom:12px; padding-bottom:8px;
    border-bottom:1px solid var(--border);
  }}

  /* Palette */
  .sv-palette {{ display:grid; grid-template-columns:repeat(5,1fr); gap:6px; }}
  .sv-p {{
    aspect-ratio:1; border-radius:7px; border:1px solid var(--border);
    font-size:.77rem; font-weight:700; cursor:pointer;
    background:var(--bg); color:var(--text-muted);
    transition:all var(--transition);
  }}
  .sv-p:hover {{ border-color:var(--blue); }}
  .sv-p.answered {{ background:var(--blue); color:#fff; border-color:var(--blue); }}
  .sv-p.skipped  {{ background:#F97316; color:#fff; border-color:#F97316; }}
  .sv-p.marked   {{ background:#9333EA; color:#fff; border-color:#9333EA; }}
  .sv-p.marked-ans{{ background:#4F46E5; color:#fff; border-color:#4F46E5; }}
  .sv-p.current  {{ box-shadow:0 0 0 2.5px var(--blue); }}

  /* Stats */
  .sv-stats {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
  .sv-stat {{ text-align:center; }}
  .sv-stat-num {{ font-size:1.5rem; font-weight:900; color:var(--blue); }}
  .sv-stat-lbl {{ font-size:.7rem; color:var(--text-muted); margin-top:2px; }}

  /* Legend */
  .sv-legend {{ display:flex; flex-direction:column; gap:7px; }}
  .sv-leg-item {{ display:flex; align-items:center; gap:8px; font-size:.79rem; color:var(--text); }}
  .sv-leg-dot {{ width:13px; height:13px; border-radius:3px; flex-shrink:0; }}

  /* Score Screen */
  #sv-score {{ display:none; flex-direction:column; align-items:center;
    justify-content:center; min-height:80vh; padding:40px 20px; text-align:center; }}
  #sv-score.show {{ display:flex; }}
  .sv-score-icon {{ font-size:4.5rem; margin-bottom:14px; }}
  .sv-score-title {{ font-size:1.9rem; font-weight:900; color:var(--blue); margin-bottom:4px; }}
  .sv-score-sub {{ font-size:.95rem; color:var(--text-muted); margin-bottom:28px; }}
  .sv-score-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr));
    gap:14px; max-width:560px; width:100%; margin-bottom:28px; }}
  .sv-score-card {{ background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); padding:18px 14px; box-shadow:var(--shadow); }}
  .sv-score-card .val {{ font-size:1.9rem; font-weight:900; }}
  .sv-score-card .lbl {{ font-size:.73rem; color:var(--text-muted); margin-top:3px; }}
  .sv-score-card.blue .val {{ color:var(--blue); }}
  .sv-score-card.green .val {{ color:#16A34A; }}
  .sv-score-card.red .val {{ color:#DC2626; }}
  .sv-score-card.gray .val {{ color:var(--text-muted); }}

  ::-webkit-scrollbar {{ width:5px; }}
  ::-webkit-scrollbar-thumb {{ background:var(--border); border-radius:99px; }}
</style>
</head>
<body>
<div id="app">

  <!-- Header -->
  <header class="sienova-header">
    <div class="sh-brand">
      <span class="logo">{b['logo_emoji']}</span>
      <span>{b['name']}</span>
    </div>
    <div class="sh-right">
      <span class="q-counter" id="sv-q-counter">Q1 / {total}</span>
      <span id="sv-timer" class="timer-pill">60:00</span>
    </div>
  </header>

  <!-- Quiz Layout -->
  <div id="sv-quiz">
    <div class="sv-wrap">

      <!-- Question Section -->
      <div class="q-section">
        <div class="q-meta">
          <span class="q-badge" id="sv-q-badge">Question 1 of {total}</span>
          <span class="marks-tag" id="sv-marks">1 Mark</span>
        </div>

        <div class="q-card">
          <p class="q-text" id="sv-q-text">Loading...</p>
          <div class="opts" id="sv-opts"></div>
          <div class="sv-solution" id="sv-sol">
            <div class="sv-sol-lbl">💡 Explanation</div>
            <div class="sv-sol-text" id="sv-sol-text"></div>
          </div>
        </div>

        <div class="q-actions">
          <button class="btn btn-outline" id="sv-prev" onclick="svPrev()">← Previous</button>
          <button class="btn btn-outline" id="sv-next" onclick="svNext()">Next →</button>
          <button class="btn btn-outline" onclick="svMark()">🔖 Mark for Review</button>
          <button class="btn btn-outline" onclick="svClear()">✕ Clear</button>
          <button class="btn btn-red btn-ml-auto" onclick="svConfirmSubmit()">Submit →</button>
        </div>
      </div>

      <!-- Sidebar -->
      <div class="sv-sidebar">

        <div class="sv-card">
          <div class="sv-card-title">📈 Progress</div>
          <div class="sv-stats">
            <div class="sv-stat"><div class="sv-stat-num" id="sv-s-ans">0</div><div class="sv-stat-lbl">Answered</div></div>
            <div class="sv-stat"><div class="sv-stat-num" id="sv-s-skp">0</div><div class="sv-stat-lbl">Skipped</div></div>
            <div class="sv-stat"><div class="sv-stat-num" id="sv-s-mrk">0</div><div class="sv-stat-lbl">Marked</div></div>
            <div class="sv-stat"><div class="sv-stat-num" id="sv-s-nv">0</div><div class="sv-stat-lbl">Not Visited</div></div>
          </div>
        </div>

        <div class="sv-card">
          <div class="sv-card-title">Question Palette</div>
          <div class="sv-palette" id="sv-palette"></div>
        </div>

        <div class="sv-card">
          <div class="sv-card-title">Legend</div>
          <div class="sv-legend">
            <div class="sv-leg-item"><div class="sv-leg-dot" style="background:var(--blue)"></div>Answered</div>
            <div class="sv-leg-item"><div class="sv-leg-dot" style="background:#F97316"></div>Skipped</div>
            <div class="sv-leg-item"><div class="sv-leg-dot" style="background:#9333EA"></div>Marked</div>
            <div class="sv-leg-item"><div class="sv-leg-dot" style="background:#4F46E5"></div>Marked + Answered</div>
            <div class="sv-leg-item"><div class="sv-leg-dot" style="background:var(--bg);border:1px solid var(--border)"></div>Not Visited</div>
          </div>
        </div>

      </div>
    </div>
  </div>

  <!-- Score Screen -->
  <div id="sv-score">
    <div class="sv-score-icon">📘</div>
    <div class="sv-score-title" id="sv-grade">Well Done!</div>
    <div class="sv-score-sub" id="sv-grade-sub">Test Submitted</div>
    <div class="sv-score-grid">
      <div class="sv-score-card blue"><div class="val" id="sv-sc-score">0</div><div class="lbl">Score</div></div>
      <div class="sv-score-card green"><div class="val" id="sv-sc-correct">0</div><div class="lbl">Correct</div></div>
      <div class="sv-score-card red"><div class="val" id="sv-sc-wrong">0</div><div class="lbl">Wrong</div></div>
      <div class="sv-score-card gray"><div class="val" id="sv-sc-unattempted">0</div><div class="lbl">Unattempted</div></div>
    </div>
    <div style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center;">
      <button class="btn btn-blue" onclick="svReview()">Review Answers</button>
      <button class="btn btn-outline" onclick="location.reload()">Restart</button>
    </div>
  </div>

</div>

<script>
const quizData = {js_data};

let cur = 0, svSubmitted = false;
const svState   = new Array(quizData.length).fill(0);
const svAnswers = new Array(quizData.length).fill(null);
let svTimer = 3600, svTimerInt;

function svInit() {{
  svBuildPalette();
  svRenderQ(0);
  svStartTimer();
}}

function svStartTimer() {{
  svTimerInt = setInterval(() => {{
    svTimer--;
    if (svTimer <= 0) {{ clearInterval(svTimerInt); svSubmit(); return; }}
    const m = String(Math.floor(svTimer/60)).padStart(2,'0');
    const s = String(svTimer%60).padStart(2,'0');
    const el = document.getElementById('sv-timer');
    el.textContent = m+':'+s;
    if (svTimer <= 300) el.classList.add('warning');
  }}, 1000);
}}

function svBuildPalette() {{
  const g = document.getElementById('sv-palette'); g.innerHTML = '';
  quizData.forEach((_, i) => {{
    const b = document.createElement('button');
    b.className = 'sv-p'; b.textContent = i+1; b.id = 'svp-'+i;
    b.onclick = () => svRenderQ(i);
    g.appendChild(b);
  }});
  svRefreshPalette();
}}

function svRefreshPalette() {{
  quizData.forEach((_, i) => {{
    const b = document.getElementById('svp-'+i); if (!b) return;
    b.className = 'sv-p';
    const s = svState[i];
    if      (s===1) b.classList.add('answered');
    else if (s===2) b.classList.add('skipped');
    else if (s===3) b.classList.add('marked');
    else if (s===4) b.classList.add('marked-ans');
    if (i===cur) b.classList.add('current');
  }});
  const ans = svState.filter(s=>s===1||s===4).length;
  const skp = svState.filter(s=>s===2).length;
  const mrk = svState.filter(s=>s===3||s===4).length;
  const nv  = svState.filter(s=>s===0).length;
  document.getElementById('sv-s-ans').textContent = ans;
  document.getElementById('sv-s-skp').textContent = skp;
  document.getElementById('sv-s-mrk').textContent = mrk;
  document.getElementById('sv-s-nv').textContent  = nv;
}}

function svRenderQ(idx) {{
  cur = idx;
  if (svState[idx]===0) svState[idx] = 2;
  const q = quizData[idx];
  document.getElementById('sv-q-badge').textContent = `Question ${{idx+1}} of ${{quizData.length}}`;
  document.getElementById('sv-q-counter').textContent = `Q${{idx+1}} / ${{quizData.length}}`;
  document.getElementById('sv-marks').textContent = `${{q.marks||1}} Mark${{q.marks!==1?'s':''}}`;
  document.getElementById('sv-q-text').textContent = q.question_text || '';
  const opts = document.getElementById('sv-opts'); opts.innerHTML='';
  (q.options||[]).forEach(opt => {{
    const b = document.createElement('button');
    b.className='opt'; b.dataset.label = opt.label;
    b.innerHTML = `<span class="opt-lbl">${{opt.label}}</span><span class="opt-txt">${{opt.text}}</span>`;
    if (svSubmitted) {{
      if (opt.label===q.correct_answer) b.classList.add('correct');
      else if (svAnswers[idx]===opt.label) b.classList.add('wrong');
      b.disabled=true;
    }} else {{
      if (svAnswers[idx]===opt.label) b.classList.add('selected');
      b.onclick = () => svSelect(idx, opt.label);
    }}
    opts.appendChild(b);
  }});
  const solBox = document.getElementById('sv-sol');
  document.getElementById('sv-sol-text').textContent = q.solution || '';
  if (svSubmitted && q.solution) solBox.classList.add('show');
  else solBox.classList.remove('show');
  document.getElementById('sv-prev').disabled = idx===0;
  document.getElementById('sv-next').disabled = idx===quizData.length-1;
  svRefreshPalette();
}}

function svSelect(qIdx, label) {{
  if (svSubmitted) return;
  svAnswers[qIdx] = label;
  svState[qIdx] = svState[qIdx]===3?4:1;
  svRenderQ(qIdx);
}}

function svPrev() {{ if (cur>0) svRenderQ(cur-1); }}
function svNext() {{
  if (svState[cur]===0||svState[cur]===2) svState[cur]=2;
  if (cur<quizData.length-1) svRenderQ(cur+1);
}}
function svMark() {{ svState[cur]=svAnswers[cur]?4:3; svRefreshPalette(); }}
function svClear() {{ svAnswers[cur]=null; svState[cur]=2; svRenderQ(cur); }}

function svConfirmSubmit() {{
  const ua = svAnswers.filter(a=>!a).length;
  if (confirm(ua>0?`${{ua}} question(s) unanswered. Submit?`:'Submit the test?')) svSubmit();
}}

function svSubmit() {{
  clearInterval(svTimerInt); svSubmitted=true;
  let correct=0,wrong=0,unattempted=0;
  quizData.forEach((q,i) => {{
    if (!svAnswers[i]) unattempted++;
    else if (svAnswers[i]===q.correct_answer) correct++;
    else wrong++;
  }});
  const score = correct - wrong*0.25;
  document.getElementById('sv-quiz').style.display='none';
  const ss = document.getElementById('sv-score'); ss.classList.add('show');
  document.getElementById('sv-sc-score').textContent   = score.toFixed(2);
  document.getElementById('sv-sc-correct').textContent  = correct;
  document.getElementById('sv-sc-wrong').textContent    = wrong;
  document.getElementById('sv-sc-unattempted').textContent = unattempted;
  const pct = (correct/quizData.length)*100;
  const [g,s] = pct>=90?['Outstanding! 🌟','Top performer!']:pct>=75?['Excellent! 📘','Great work!']:pct>=60?['Good Effort 👍','Keep it up!']:pct>=40?['Keep Practicing 💪','Revise concepts.']:['Needs Revision 📚','Focus on basics.'];
  document.getElementById('sv-grade').textContent=g;
  document.getElementById('sv-grade-sub').textContent=`${{s}} (${{pct.toFixed(1)}}%)`;
}}

function svReview() {{
  document.getElementById('sv-score').classList.remove('show');
  document.getElementById('sv-quiz').style.display='';
  svRenderQ(0);
}}

svInit();
</script>
</body>
</html>"""
