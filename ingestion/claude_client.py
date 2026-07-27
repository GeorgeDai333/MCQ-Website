import anthropic
from django.conf import settings

TOOL_NAME = "record_question_bank"
MODEL = "claude-sonnet-5"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Record the structured multiple-choice question bank extracted from "
        "raw quiz text, including each question's correct answer taken from "
        "the trailing answer key."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_number": {"type": "integer"},
                        "question_text": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "text": {"type": "string"},
                                },
                                "required": ["label", "text"],
                            },
                        },
                        "correct_label": {"type": "string"},
                    },
                    "required": [
                        "question_number",
                        "question_text",
                        "options",
                        "correct_label",
                    ],
                },
            }
        },
        "required": ["questions"],
    },
}

SYSTEM_PROMPT = (
    "You are extracting a multiple-choice question bank and its answer key "
    "from raw text pasted from a teacher's quiz file. Each question has "
    "2-6 lettered options (A, B, C, ...). An answer key appears at the end "
    "of the document mapping question numbers to correct option letters -- "
    "attach the correct letter to each corresponding question as "
    "correct_label. Return ONLY structured data via the record_question_bank "
    "tool. Do not emit the answer key itself as a separate question."
)

_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class IngestionAPIError(Exception):
    """Raised when the Claude API call fails outright (not a content/parse issue)."""


def call_claude_for_questions(raw_text: str) -> list[dict]:
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise IngestionAPIError("ANTHROPIC_API_KEY is not configured.")

    client = anthropic.Anthropic(api_key=api_key)

    response = None
    last_exc = None
    for attempt_num in range(2):  # one automatic retry on transient errors only
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                tools=[TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[{"role": "user", "content": raw_text}],
            )
            break
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
            last_exc = exc
            is_transient = isinstance(exc, anthropic.APIConnectionError) or (
                isinstance(exc, anthropic.APIStatusError)
                and exc.status_code in _TRANSIENT_STATUS_CODES
            )
            if attempt_num == 0 and is_transient:
                continue
            break

    if response is None:
        raise IngestionAPIError(f"Claude API call failed: {last_exc}")

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == TOOL_NAME:
            return block.input.get("questions", [])

    raise IngestionAPIError("Claude did not return a structured tool call.")
