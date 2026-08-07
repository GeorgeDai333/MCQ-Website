from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Quiz(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    ASSIGNMENT_ALL = "all"
    ASSIGNMENT_SPECIFIC = "specific"
    ASSIGNMENT_CHOICES = [
        (ASSIGNMENT_ALL, "All students"),
        (ASSIGNMENT_SPECIFIC, "Specific students"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quizzes",
    )
    title = models.CharField(max_length=200)
    duration_minutes = models.PositiveIntegerField(
        help_text="How long a student has once they start the quiz."
    )
    passing_score = models.PositiveIntegerField(
        help_text="Minimum percentage (0-100) correct required to pass."
    )
    quiz_length = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Number of questions sampled from the bank per attempt. Leave "
            "blank to include every question in the bank on every attempt."
        ),
    )
    allow_retake = models.BooleanField(
        default=False,
        help_text="Whether a student may retake this quiz after finishing it, "
        "whether they passed or failed.",
    )
    show_class_average = models.BooleanField(default=False)
    show_answers_after_close = models.BooleanField(
        default=False,
        help_text="Once the quiz's closing time has passed, let students "
        "review their own answers alongside the correct answers on their "
        "results page.",
    )
    opening_time = models.DateTimeField()
    closing_time = models.DateTimeField(
        help_text="When the quiz stops accepting new attempts from students."
    )
    expiration_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "When the quiz (and its question bank, attempts, and results) is "
            "permanently deleted. This is separate from the closing time -- "
            "students are locked out at closing time, but the quiz and its "
            "data stick around until it expires. Leave blank to keep it "
            "indefinitely."
        ),
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    assignment = models.CharField(
        max_length=10, choices=ASSIGNMENT_CHOICES, default=ASSIGNMENT_ALL
    )
    assigned_students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="assigned_quizzes",
        blank=True,
        help_text="Only used when assignment is 'Specific students'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "opening_time", "closing_time"]),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if self.opening_time and self.closing_time:
            if self.closing_time <= self.opening_time:
                raise ValidationError(
                    {"closing_time": "Closing time must be after opening time."}
                )
        if self.expiration_time and self.closing_time:
            if self.expiration_time <= self.closing_time:
                raise ValidationError(
                    {"expiration_time": "Expiration time must be after closing time."}
                )
        if self.passing_score is not None and not (0 <= self.passing_score <= 100):
            raise ValidationError(
                {"passing_score": "Passing score must be between 0 and 100."}
            )

    @property
    def is_locked(self):
        """Single source of truth reconciling the spec's two edit-lock
        conditions: opening time has passed, OR at least one attempt has
        already been created. Whichever trips first wins.
        """
        return timezone.now() >= self.opening_time or self.attempts.exists()

    @property
    def is_open_for_students(self):
        now = timezone.now()
        return (
            self.status == self.STATUS_ACTIVE
            and self.opening_time <= now <= self.closing_time
        )

    @property
    def is_expired(self):
        return self.expiration_time is not None and timezone.now() >= self.expiration_time

    @property
    def answers_reviewable(self):
        """Whether a student may see their answers next to the correct ones
        on their results page -- gated on the teacher's toggle AND the quiz
        having actually closed, so early finishers can't see (and leak)
        correct answers while others are still eligible to take it.
        """
        return self.show_answers_after_close and timezone.now() >= self.closing_time

    def is_visible_to(self, user):
        if self.assignment == self.ASSIGNMENT_ALL:
            return True
        return self.assigned_students.filter(pk=user.pk).exists()


class QuestionBankItem(models.Model):
    """The persistent pool of questions a quiz samples from. Not per-attempt."""

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="bank_items")
    order_hint = models.PositiveIntegerField(
        default=0, help_text="Original position in the uploaded file (display only)."
    )
    question_text = models.TextField()
    options = models.JSONField(
        help_text='List of {"label": "A", "text": "..."} dicts, in bank order.'
    )
    correct_label = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order_hint", "id"]

    def __str__(self):
        return f"[{self.quiz_id}] {self.question_text[:50]}"

    def clean(self):
        labels = [opt.get("label") for opt in (self.options or [])]
        if not (2 <= len(labels) <= 6):
            raise ValidationError({"options": "Each question needs 2-6 options."})
        if self.correct_label not in labels:
            raise ValidationError(
                {"correct_label": "Correct label must match one of the options."}
            )


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    deadline_at = models.DateTimeField(
        help_text="Authoritative deadline: min(started_at + duration, closing_time), "
        "computed once at attempt creation."
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    auto_submitted = models.BooleanField(default=False)
    score_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    passed = models.BooleanField(null=True, blank=True)
    retake_granted_by_teacher = models.BooleanField(
        default=False,
        help_text="A teacher-granted exception letting this specific student "
        "retake the quiz once even though it doesn't allow retakes generally. "
        "Only applies while this is the student's latest attempt.",
    )

    class Meta:
        indexes = [
            models.Index(fields=["quiz", "student", "started_at"]),
            models.Index(fields=["student", "submitted_at"]),
        ]

    def __str__(self):
        return f"{self.student} / {self.quiz} @ {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def is_in_progress(self):
        return self.submitted_at is None


class AttemptQuestion(models.Model):
    """The frozen, per-attempt sampled + shuffled question actually served."""

    attempt = models.ForeignKey(
        QuizAttempt, on_delete=models.CASCADE, related_name="questions"
    )
    # CASCADE, not PROTECT: a whole quiz (bank items included) must always be
    # deletable per spec, even when locked/attempted. There's no standalone
    # "edit/delete one bank item" flow in v1 that this would otherwise guard.
    bank_item = models.ForeignKey(QuestionBankItem, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(help_text="1-based presentation order.")
    shuffled_options = models.JSONField(
        help_text="Options re-shuffled and re-lettered A, B, C... for this attempt."
    )
    correct_label = models.CharField(
        max_length=4, help_text="Re-lettered correct label for this attempt."
    )

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "position"], name="unique_attempt_position"
            )
        ]

    def __str__(self):
        return f"Q{self.position} of attempt {self.attempt_id}"


class AttemptAnswer(models.Model):
    """The student's saved/submitted choice for one AttemptQuestion."""

    attempt_question = models.OneToOneField(
        AttemptQuestion, on_delete=models.CASCADE, related_name="answer"
    )
    selected_label = models.CharField(max_length=4, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Answer for {self.attempt_question_id} = {self.selected_label}"
