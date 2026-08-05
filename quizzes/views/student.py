from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import AttemptAnswer, Quiz, QuizAttempt
from ..permissions import require_attempt_owner
from ..services.grading import ensure_not_expired, grade_and_submit
from ..services.sampling import AttemptInProgressError, start_attempt


def _save_answers_from_post(attempt, post_data):
    questions = list(attempt.questions.select_related("answer"))
    now = timezone.now()
    to_update = []
    for aq in questions:
        value = post_data.get(f"q_{aq.id}")
        valid_labels = {opt["label"] for opt in aq.shuffled_options}
        if value in valid_labels and aq.answer.selected_label != value:
            aq.answer.selected_label = value
            aq.answer.updated_at = now
            to_update.append(aq.answer)
    if to_update:
        AttemptAnswer.objects.bulk_update(to_update, ["selected_label", "updated_at"])


@login_required
def student_dashboard(request):
    now = timezone.now()
    available_quizzes = list(
        Quiz.objects.filter(
            status=Quiz.STATUS_ACTIVE, opening_time__lte=now, closing_time__gte=now
        )
        .filter(Q(assignment=Quiz.ASSIGNMENT_ALL) | Q(assigned_students=request.user))
        .distinct()
    )

    rows = []
    for quiz in available_quizzes:
        latest = (
            quiz.attempts.filter(student=request.user).order_by("-started_at").first()
        )
        if latest is not None:
            ensure_not_expired(latest)
            latest.refresh_from_db()
        class_average = None
        if quiz.show_class_average:
            agg = quiz.attempts.filter(submitted_at__isnull=False).aggregate(
                avg=Avg("score_percent")
            )
            class_average = agg["avg"]
        rows.append({"quiz": quiz, "attempt": latest, "class_average": class_average})

    available_ids = {quiz.pk for quiz in available_quizzes}
    history_quizzes = (
        Quiz.objects.filter(attempts__student=request.user)
        .exclude(pk__in=available_ids)
        .distinct()
    )
    history_rows = []
    for quiz in history_quizzes:
        latest = (
            quiz.attempts.filter(student=request.user).order_by("-started_at").first()
        )
        history_rows.append({"quiz": quiz, "attempt": latest})

    return render(
        request,
        "quizzes/student_dashboard.html",
        {"rows": rows, "history_rows": history_rows},
    )


@login_required
@require_http_methods(["POST"])
def student_start_attempt(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)

    if not quiz.is_open_for_students or not quiz.is_visible_to(request.user):
        messages.error(request, "This quiz is not currently open.")
        return redirect("quizzes:student_dashboard")

    latest = (
        quiz.attempts.filter(student=request.user).order_by("-started_at").first()
    )
    if latest is not None:
        ensure_not_expired(latest)
        latest.refresh_from_db()
        if latest.submitted_at is None:
            return redirect("quizzes:student_take_attempt", pk=latest.pk)
        if latest.passed:
            messages.info(request, "You've already passed this quiz.")
            return redirect("quizzes:student_dashboard")
        if not quiz.allow_retake_on_fail:
            messages.error(request, "Retakes are not allowed for this quiz.")
            return redirect("quizzes:student_dashboard")

    try:
        attempt = start_attempt(quiz, request.user)
    except AttemptInProgressError:
        in_progress = quiz.attempts.filter(
            student=request.user, submitted_at__isnull=True
        ).first()
        return redirect("quizzes:student_take_attempt", pk=in_progress.pk)

    return redirect("quizzes:student_take_attempt", pk=attempt.pk)


@login_required
def student_take_attempt(request, pk):
    attempt = get_object_or_404(QuizAttempt, pk=pk)
    require_attempt_owner(attempt, request.user)
    ensure_not_expired(attempt)
    attempt.refresh_from_db()

    if attempt.submitted_at is not None:
        return redirect("quizzes:student_attempt_results", pk=attempt.pk)

    questions = attempt.questions.select_related("answer", "bank_item").order_by(
        "position"
    )
    return render(
        request,
        "quizzes/take_attempt.html",
        {"attempt": attempt, "questions": questions},
    )


@login_required
@require_http_methods(["POST"])
def student_autosave_attempt(request, pk):
    attempt = get_object_or_404(QuizAttempt, pk=pk)
    require_attempt_owner(attempt, request.user)
    ensure_not_expired(attempt)
    attempt.refresh_from_db()

    if attempt.submitted_at is not None:
        return JsonResponse(
            {
                "status": "submitted",
                "redirect_url": reverse(
                    "quizzes:student_attempt_results", args=[attempt.pk]
                ),
            }
        )

    _save_answers_from_post(attempt, request.POST)

    return JsonResponse(
        {
            "status": "ok",
            "server_time": timezone.now().isoformat(),
            "deadline_at": attempt.deadline_at.isoformat(),
        }
    )


@login_required
@require_http_methods(["POST"])
def student_submit_attempt(request, pk):
    attempt = get_object_or_404(QuizAttempt, pk=pk)
    require_attempt_owner(attempt, request.user)
    ensure_not_expired(attempt)
    attempt.refresh_from_db()

    if attempt.submitted_at is None:
        _save_answers_from_post(attempt, request.POST)
        grade_and_submit(attempt, auto=False)

    return redirect("quizzes:student_attempt_results", pk=attempt.pk)


@login_required
def student_attempt_results(request, pk):
    attempt = get_object_or_404(QuizAttempt, pk=pk)
    require_attempt_owner(attempt, request.user)
    ensure_not_expired(attempt)
    attempt.refresh_from_db()

    if attempt.submitted_at is None:
        return redirect("quizzes:student_take_attempt", pk=attempt.pk)

    return render(request, "quizzes/attempt_results.html", {"attempt": attempt})
