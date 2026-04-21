"""
Quiz Extractor Utility
Adapted from extractor.py — uses Playwright to extract quizData from HTML files
"""

import logging
from datetime import datetime
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

LABELS = ["A", "B", "C", "D", "E", "F"]


async def extract_quiz_from_html(html_file_path: str) -> dict | None:
    """
    Load HTML in headless Chromium, extract quizData JS variable,
    and return formatted quiz dict. Returns None on failure.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        file_url = f"file://{html_file_path}"
        logger.info("Extracting from %s", file_url)

        try:
            await page.goto(file_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(3000)

            raw = await page.evaluate("""
                () => {
                    if (typeof quizData !== 'undefined' && quizData) return quizData;
                    return null;
                }
            """)

            if not raw or not isinstance(raw, list) or len(raw) == 0:
                logger.warning("No quizData found in %s", html_file_path)
                return None

            return format_data(raw, _name_from_path(html_file_path))

        except Exception as e:
            logger.error("Playwright error: %s", e)
            return None
        finally:
            await browser.close()


def format_data(raw_questions: list, test_name: str = "Quiz") -> dict:
    """
    Convert raw quizData list (from JS) to structured dict.
    Accepts both raw list and already-formatted dict (idempotent).
    """
    questions = []

    for idx, q in enumerate(raw_questions, 1):
        correct_idx = q.get("correct")
        correct_answer = (
            LABELS[correct_idx]
            if isinstance(correct_idx, int) and correct_idx < len(LABELS)
            else None
        )

        opts = q.get("options", [])
        options = []
        if isinstance(opts, list):
            for i, opt in enumerate(opts):
                if i < len(LABELS):
                    options.append({
                        "label": LABELS[i],
                        "text": str(opt or "").strip()
                    })

        questions.append({
            "id": q.get("id", idx),
            "question_number": idx,
            "question_text": (q.get("question") or "").strip(),
            "marks": q.get("marks", 1),
            "correct_answer": correct_answer,
            "options": options,
            "solution": (q.get("solution") or "").strip(),
        })

    return {
        "test_name": test_name,
        "total_questions": len(questions),
        "extracted_at": datetime.now().isoformat(),
        "questions": questions,
    }


def _name_from_path(path: str) -> str:
    from pathlib import Path
    return Path(path).stem.replace("_", " ").title()
