import random
import string
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import AttemptAnswer, AttemptQuestion, QuizAttempt


class AttemptInProgressError(Exception):
    """Raised when a student tries to start a new attempt while one is
    already in progress for this quiz (they should resume it instead)."""


def relettered_options(options: list[dict], correct_label: str) -> tuple[list[dict], str]:
    """Shuffle option order and re-letter A, B, C... in the new order, so
    on-screen, autosaved, and printed-docx labels always agree with what
    the student actually sees for this attempt. Returns (shuffled, new_correct_label).
    """
    shuffled = list(options)
    random.shuffle(shuffled)
    letters = string.ascii_uppercase
    new_correct_label = None
    relabeled = []
    for i, opt in enumerate(shuffled):
        new_label = letters[i]
        relabeled.append({"label": new_label, "text": opt["text"]})
        if opt["label"] == correct_label:
            new_correct_label = new_label
    return relabeled, new_correct_label


@transaction.atomic
def start_attempt(quiz, student) -> QuizAttempt:
    """Create a new attempt: sample quiz_length bank items, freeze their
    shuffled/re-lettered presentation, and compute the authoritative
    deadline. Guards against a second concurrent in-progress attempt.
    """
    existing_in_progress = (
        quiz.attempts.filter(student=student, submitted_at__isnull=True)
        .order_by("-started_at")
        .first()
    )
    if existing_in_progress is not None:
        raise AttemptInProgressError(
            "You already have an attempt in progress for this quiz."
        )

    bank_items = list(quiz.bank_items.all())
    # A blank quiz_length means "use every question in the bank."
    target_length = quiz.quiz_length or len(bank_items)

    # On a retake, prefer bank items the student hasn't already seen on this
    # quiz, so failing and retaking pulls a genuinely different set rather
    # than just reshuffling the same one. Falls back to the full bank once
    # there aren't enough unseen items left to fill target_length.
    seen_ids = set(
        AttemptQuestion.objects.filter(
            attempt__quiz=quiz, attempt__student=student
        ).values_list("bank_item_id", flat=True)
    )
    unseen = [item for item in bank_items if item.id not in seen_ids]
    pool = unseen if len(unseen) >= target_length else bank_items

    sampled = random.sample(pool, k=target_length)

    now = timezone.now()
    deadline_at = min(now + timedelta(minutes=quiz.duration_minutes), quiz.closing_time)

    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        student=student,
        deadline_at=deadline_at,
    )

    attempt_questions = []
    for position, bank_item in enumerate(sampled, start=1):
        shuffled_options, new_correct_label = relettered_options(
            bank_item.options, bank_item.correct_label
        )
        attempt_questions.append(
            AttemptQuestion(
                attempt=attempt,
                bank_item=bank_item,
                position=position,
                shuffled_options=shuffled_options,
                correct_label=new_correct_label,
            )
        )
    AttemptQuestion.objects.bulk_create(attempt_questions)

    AttemptAnswer.objects.bulk_create(
        AttemptAnswer(attempt_question=aq) for aq in attempt.questions.all()
    )

    return attempt
