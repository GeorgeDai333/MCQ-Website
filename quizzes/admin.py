from django.contrib import admin

from .models import AttemptAnswer, AttemptQuestion, QuestionBankItem, Quiz, QuizAttempt


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "status",
        "quiz_length",
        "passing_score",
        "opening_time",
        "closing_time",
        "expiration_time",
    )
    list_filter = ("status", "allow_retake_on_fail", "show_class_average")
    search_fields = ("title", "owner__username", "owner__email")


@admin.register(QuestionBankItem)
class QuestionBankItemAdmin(admin.ModelAdmin):
    list_display = ("quiz", "order_hint", "question_text", "correct_label")
    list_filter = ("quiz",)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "quiz",
        "student",
        "started_at",
        "deadline_at",
        "submitted_at",
        "auto_submitted",
        "score_percent",
        "passed",
    )
    list_filter = ("quiz", "passed", "auto_submitted")


@admin.register(AttemptQuestion)
class AttemptQuestionAdmin(admin.ModelAdmin):
    list_display = ("attempt", "position", "correct_label")


@admin.register(AttemptAnswer)
class AttemptAnswerAdmin(admin.ModelAdmin):
    list_display = ("attempt_question", "selected_label", "updated_at")
