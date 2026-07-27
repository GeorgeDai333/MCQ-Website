import re

from django.conf import settings

from . import extraction
from .claude_client import IngestionAPIError, call_claude_for_questions
from .schemas import IngestionResult, validate_rows


class IngestionError(Exception):
    """Raised when ingestion fails completely -- nothing usable extracted."""


def ingest(uploaded_file) -> IngestionResult:
    raw_text = extraction.extract_text(uploaded_file)

    if settings.MCQ_INGESTION_FAKE:
        raw_rows = _fake_parse(raw_text)
    else:
        try:
            raw_rows = call_claude_for_questions(raw_text)
        except IngestionAPIError as exc:
            raise IngestionError(str(exc)) from exc

    result = validate_rows(raw_rows)
    if not result.questions:
        raise IngestionError(
            "Could not extract any valid questions from this file. Please "
            "check the format (numbered questions, lettered options, and a "
            "trailing answer key) and try again."
        )
    return result


_QUESTION_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*\S)\s*$")
_OPTION_RE = re.compile(r"^\s*([A-Za-z])[.)]\s+(.*\S)\s*$")
_KEY_MARKER_RE = re.compile(r"(?i)^\s*answer\s*key\s*[:\-]?\s*$")
_KEY_LINE_RE = re.compile(r"^\s*(\d+)[.):]\s*([A-Za-z])\s*$")


def _fake_parse(raw_text: str) -> list[dict]:
    """Naive line-based parser used when MCQ_INGESTION_FAKE=1, so manual
    testing can exercise the full teacher upload -> review -> quiz flow
    without a real ANTHROPIC_API_KEY or network access.

    Expects: numbered questions each followed by lettered option lines, then
    a line "Answer Key" (or "Answer Key:"), then lines like "1. B".
    """
    questions_raw: list[dict] = []
    answer_map: dict[int, str] = {}
    mode = "questions"
    current = None

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if _KEY_MARKER_RE.match(stripped):
            mode = "answers"
            continue

        if mode == "answers":
            m = _KEY_LINE_RE.match(stripped)
            if m:
                answer_map[int(m.group(1))] = m.group(2).upper()
            continue

        m = _QUESTION_RE.match(stripped)
        if m:
            if current:
                questions_raw.append(current)
            current = {
                "question_number": int(m.group(1)),
                "question_text": m.group(2),
                "options": [],
            }
            continue

        m = _OPTION_RE.match(stripped)
        if m and current is not None:
            current["options"].append({"label": m.group(1).upper(), "text": m.group(2)})
            continue

        if current is not None and not current["options"]:
            current["question_text"] += " " + stripped

    if current:
        questions_raw.append(current)

    questions = []
    for q in questions_raw:
        correct = answer_map.get(q["question_number"])
        if q["options"] and correct:
            questions.append({**q, "correct_label": correct})
    return questions
