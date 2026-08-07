from dataclasses import asdict

from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ingestion.extraction import ExtractionError
from ingestion.services import IngestionError, ingest

from ..forms import (
    QuestionReviewFormSet,
    QuizMetadataForm,
    QuizUploadForm,
    initial_data_for_bank_items,
    initial_data_for_questions,
)
from ..models import QuestionBankItem, Quiz
from ..permissions import require_quiz_owner, teacher_required
from ..services.exports import export_attempt_docx, export_attempts_csv, export_blank_sample_docx

DRAFT_SESSION_KEY = "ingestion_draft_{}"
ERRORS_SESSION_KEY = "ingestion_errors_{}"


def _review_row_errors(formset):
    """Flatten a review formset's per-row errors into a summary the
    template can render next to the save buttons -- with a full formset,
    the row an error is actually on can easily be scrolled out of view.
    """
    summary = []
    for i, form in enumerate(formset, start=1):
        if not form.errors:
            continue
        messages_list = []
        for field, errors in form.errors.items():
            if field == "__all__":
                messages_list.extend(errors)
            else:
                label = form.fields[field].label or field
                messages_list.extend(f"{label}: {error}" for error in errors)
        preview = (form["question_text"].value() or "").strip()
        summary.append(
            {
                "row_number": i,
                "anchor": form.prefix,
                "preview": preview[:60] or "(blank question)",
                "messages": messages_list,
            }
        )
    return summary


@teacher_required
def teacher_dashboard(request):
    quizzes = request.user.quizzes.order_by("-created_at")
    return render(request, "quizzes/teacher_dashboard.html", {"quizzes": quizzes})


@teacher_required
def teacher_quiz_create(request):
    if request.method == "POST":
        form = QuizMetadataForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.owner = request.user
            quiz.status = Quiz.STATUS_DRAFT
            quiz.save()
            form.save_m2m()
            if "save_and_quit" in request.POST:
                messages.success(
                    request, "Quiz saved as a draft. Continue it anytime from your dashboard."
                )
                return redirect("quizzes:teacher_dashboard")
            return redirect("quizzes:teacher_quiz_upload", pk=quiz.pk)
    else:
        form = QuizMetadataForm()
    return render(
        request,
        "quizzes/teacher_quiz_form.html",
        {"form": form, "mode": "create"},
    )


@teacher_required
def teacher_quiz_upload(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    require_quiz_owner(quiz, request.user)
    if quiz.status != Quiz.STATUS_DRAFT:
        messages.info(request, "This quiz has already been ingested.")
        return redirect("quizzes:teacher_quiz_review", pk=quiz.pk)

    error = None
    if request.method == "POST":
        form = QuizUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                result = ingest(form.cleaned_data["bank_file"])
            except (ExtractionError, IngestionError) as exc:
                error = str(exc)
            else:
                request.session[DRAFT_SESSION_KEY.format(quiz.pk)] = [
                    q.model_dump() for q in result.questions
                ]
                request.session[ERRORS_SESSION_KEY.format(quiz.pk)] = [
                    asdict(e) for e in result.errors
                ]
                return redirect("quizzes:teacher_quiz_review", pk=quiz.pk)
    else:
        form = QuizUploadForm()

    return render(
        request,
        "quizzes/teacher_quiz_upload.html",
        {"quiz": quiz, "form": form, "error": error},
    )


@teacher_required
def teacher_quiz_review(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    require_quiz_owner(quiz, request.user)

    draft_questions = request.session.get(DRAFT_SESSION_KEY.format(quiz.pk))
    parse_errors = request.session.get(ERRORS_SESSION_KEY.format(quiz.pk), [])

    if quiz.status != Quiz.STATUS_DRAFT:
        messages.info(request, "This quiz has already been confirmed.")
        return redirect("quizzes:teacher_dashboard")

    resuming_saved_progress = False
    if draft_questions is None:
        if quiz.bank_items.exists():
            resuming_saved_progress = True
        else:
            messages.warning(request, "Please upload a question bank file first.")
            return redirect("quizzes:teacher_quiz_upload", pk=quiz.pk)

    row_errors = []
    if request.method == "POST":
        formset = QuestionReviewFormSet(request.POST)
        if formset.is_valid():
            surviving = [
                f.cleaned_data
                for f in formset
                if not f.cleaned_data.get("delete")
                and not f.cleaned_data.get("_blank")
            ]
            save_and_quit = "save_and_quit" in request.POST
            required_minimum = quiz.quiz_length if quiz.quiz_length else 1
            if not save_and_quit and len(surviving) < required_minimum:
                if quiz.quiz_length:
                    messages.error(
                        request,
                        f"Quiz length is {quiz.quiz_length}, but only "
                        f"{len(surviving)} question(s) remain after review. "
                        "Add more questions or lower the quiz length.",
                    )
                else:
                    messages.error(
                        request, "Add at least one question before confirming the quiz."
                    )
            else:
                with transaction.atomic():
                    QuestionBankItem.objects.filter(quiz=quiz).delete()
                    for i, data in enumerate(surviving):
                        QuestionBankItem.objects.create(
                            quiz=quiz,
                            order_hint=i,
                            question_text=data["question_text"],
                            options=data["_options"],
                            correct_label=data["correct_label"],
                        )
                    if not save_and_quit:
                        quiz.status = Quiz.STATUS_ACTIVE
                        quiz.save(update_fields=["status"])
                request.session.pop(DRAFT_SESSION_KEY.format(quiz.pk), None)
                request.session.pop(ERRORS_SESSION_KEY.format(quiz.pk), None)
                if save_and_quit:
                    messages.success(
                        request,
                        "Progress saved as a draft. Continue reviewing anytime from your dashboard.",
                    )
                else:
                    messages.success(request, "Quiz confirmed and activated.")
                return redirect("quizzes:teacher_dashboard")
        else:
            row_errors = _review_row_errors(formset)
    elif resuming_saved_progress:
        formset = QuestionReviewFormSet(
            initial=initial_data_for_bank_items(quiz.bank_items.all())
        )
    else:
        formset = QuestionReviewFormSet(
            initial=initial_data_for_questions(draft_questions)
        )

    return render(
        request,
        "quizzes/teacher_quiz_review.html",
        {
            "quiz": quiz,
            "formset": formset,
            "parse_errors": parse_errors,
            "row_errors": row_errors,
        },
    )


@teacher_required
def teacher_quiz_edit(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    require_quiz_owner(quiz, request.user)

    if quiz.is_locked:
        reasons = []
        if timezone.now() >= quiz.opening_time:
            reasons.append("its opening time has passed")
        if quiz.attempts.exists():
            reasons.append("at least one student has already attempted it")
        messages.error(
            request,
            "This quiz can no longer be edited because " + " and ".join(reasons) + ".",
        )
        return redirect("quizzes:teacher_dashboard")

    if request.method == "POST":
        form = QuizMetadataForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, "Quiz updated.")
            return redirect("quizzes:teacher_dashboard")
    else:
        form = QuizMetadataForm(instance=quiz)

    return render(
        request,
        "quizzes/teacher_quiz_form.html",
        {"form": form, "mode": "edit", "quiz": quiz},
    )


@teacher_required
@require_http_methods(["GET", "POST"])
def teacher_quiz_delete(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    require_quiz_owner(quiz, request.user)

    if request.method == "POST":
        quiz.delete()
        messages.success(request, "Quiz deleted.")
        return redirect("quizzes:teacher_dashboard")

    return render(request, "quizzes/teacher_quiz_confirm_delete.html", {"quiz": quiz})


@teacher_required
def teacher_quiz_export_csv(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    require_quiz_owner(quiz, request.user)
    return export_attempts_csv(quiz)


@teacher_required
def teacher_quiz_export_docx(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    require_quiz_owner(quiz, request.user)

    attempt_id = request.GET.get("attempt")
    if attempt_id:
        attempt = get_object_or_404(quiz.attempts, pk=attempt_id)
        return export_attempt_docx(attempt)

    if request.GET.get("new_sample"):
        if quiz.quiz_length and quiz.bank_items.count() < quiz.quiz_length:
            raise Http404("Quiz does not have enough bank items to sample.")
        if not quiz.bank_items.exists():
            raise Http404("Quiz has no bank items to sample.")
        return export_blank_sample_docx(quiz)

    messages.error(request, "Specify ?attempt=<id> or ?new_sample=1.")
    return redirect("quizzes:teacher_dashboard")
