"""
PDF Quiz Parser
Extracts questions, options, correct answers and solutions from
IBPS-style PDF quiz files (Guidely / JethaBanker format).

Structure expected:
  - Questions section: "N. Questions\n<text>\na. opt\nb. opt..."
  - Explanations section after "Explanations:" header
  - Answer format: "Answer: B" or "Answer: B (some text)"
"""

import re
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Lines to strip (headers, footers, watermarks)
_NOISE = re.compile(
    r'^(IBPS\s+PO.*|Page\s+\d+.*|@JethaBanker.*|Guidely.*|Get it on.*|Google Play.*)\s*$',
    re.MULTILINE | re.IGNORECASE
)

LABELS = ["A", "B", "C", "D", "E", "F"]


def parse_pdf(pdf_path: str, test_name: str | None = None) -> dict | None:
    """
    Parse a PDF quiz file and return quiz_data dict compatible with build_html().
    Returns None on failure.
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        return None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(
                (p.extract_text() or "") for p in pdf.pages
            )
    except Exception as e:
        logger.error("Failed to read PDF %s: %s", pdf_path, e)
        return None

    if not full_text.strip():
        logger.warning("No text extracted from %s", pdf_path)
        return None

    # Split questions / explanations
    exp_idx = full_text.find("Explanations:")
    if exp_idx == -1:
        # Try alternate spellings
        for marker in ["Explanation:", "EXPLANATIONS:", "EXPLANATION:"]:
            exp_idx = full_text.find(marker)
            if exp_idx != -1:
                break

    q_raw   = full_text[:exp_idx] if exp_idx != -1 else full_text
    ex_raw  = full_text[exp_idx:] if exp_idx != -1 else ""

    questions  = _parse_questions(q_raw)
    answer_map = _parse_explanations(ex_raw)

    if not questions:
        logger.warning("No questions found in %s", pdf_path)
        return None

    # Merge answers + solutions into questions
    for q in questions:
        ans = answer_map.get(q["question_number"], {})
        q["correct_answer"] = ans.get("correct_answer")
        q["solution"]       = ans.get("solution", "")

    name = test_name or Path(pdf_path).stem.replace("_", " ").strip()

    return {
        "test_name":       name,
        "total_questions": len(questions),
        "extracted_at":    datetime.now().isoformat(),
        "duration_sec":    20 * 60,  # 20 minutes for PDF quizzes
        "questions":       questions,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Remove noise lines (headers/footers/watermarks)."""
    return _NOISE.sub("", text)


def _parse_questions(raw: str) -> list:
    clean = _clean(raw)
    # Split on "N. Questions" markers
    blocks = re.split(r'\n(\d+)\. Questions\n', clean)
    # blocks = [preamble, '1', body1, '2', body2, ...]

    questions = []
    for i in range(1, len(blocks) - 1, 2):
        num  = int(blocks[i])
        body = blocks[i + 1].strip()

        # Extract options: lines starting with "a. ", "b. " etc.
        opts_raw = re.findall(
            r'\n([a-e])\. (.+?)(?=\n[a-e]\. |\Z)',
            "\n" + body,
            re.DOTALL
        )
        options = [
            {"label": lbl.upper(), "text": txt.strip().replace("\n", " ")}
            for lbl, txt in opts_raw
        ]

        # Question text = everything before first option line
        first_opt = re.search(r'\n[a-e]\. ', body)
        q_text = body[:first_opt.start()].strip() if first_opt else body.strip()
        q_text = q_text.replace("\n", " ").strip()

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


def _parse_explanations(raw: str) -> dict:
    """Returns {question_number: {correct_answer, solution}}"""
    if not raw.strip():
        return {}

    clean = _clean(raw)
    blocks = re.split(r'\n(\d+)\. Questions\n', clean)

    result = {}
    for i in range(1, len(blocks) - 1, 2):
        num  = int(blocks[i])
        body = blocks[i + 1].strip()

        # Extract answer letter
        ans_match = re.search(r'Answer:\s*([A-Ea-e])', body)
        letter = ans_match.group(1).upper() if ans_match else None

        # Solution = everything after the first "Answer:" line
        lines = body.split("\n")
        sol_lines = []
        found_ans = False
        for line in lines:
            if not found_ans and re.search(r'Answer:\s*[A-Ea-e]', line):
                found_ans = True
                # Include rest of this line after "Answer: X ..."
                # (usually the answer label text)
                continue
            if found_ans:
                sol_lines.append(line)

        solution = "\n".join(sol_lines).strip()
        # Clean up common noise in solution
        solution = re.sub(r'Analysis of Other Options:\n?', '', solution)
        solution = solution.strip()

        result[num] = {
            "correct_answer": letter,
            "solution":       solution,
        }

    return result
