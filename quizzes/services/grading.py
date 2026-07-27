from django.db import transaction
from django.utils import timezone

from ..models import QuizAttempt


def ensure_not_expired(attempt: QuizAttempt) -> QuizAttempt:
    """The server is the sole authority on attempt expiry -- never the
    client-side timer. Call this at the top of every view/endpoint that
    touches an in-progress attempt. If time's up, auto-grade and submit it
    right here, so expiry is self-healing on next touch with no background
    worker required.
    """
    if attempt.submitted_at is None and timezone.now() >= attempt.deadline_at:
        grade_and_submit(attempt, auto=True)
        attempt.refresh_from_db()
    return attempt


@transaction.atomic
def grade_and_submit(attempt: QuizAttempt, auto: bool) -> QuizAttempt:
    if attempt.submitted_at is not None:
        return attempt

    questions = list(attempt.questions.select_related("answer"))
    correct_count = sum(
        1
        for q in questions
        if q.answer.selected_label is not None
        and q.answer.selected_label == q.correct_label
    )
    total = len(questions)
    score_percent = (100 * correct_count / total) if total else 0

    attempt.score_percent = score_percent
    attempt.passed = score_percent >= attempt.quiz.passing_score
    attempt.submitted_at = timezone.now()
    attempt.auto_submitted = auto
    attempt.save(
        update_fields=["score_percent", "passed", "submitted_at", "auto_submitted"]
    )
    return attempt
