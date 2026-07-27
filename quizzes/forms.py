from django import forms

from .models import Quiz

OPTION_LETTERS = "ABCDEF"


class QuizMetadataForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = [
            "title",
            "duration_minutes",
            "passing_score",
            "quiz_length",
            "allow_retake_on_fail",
            "show_class_average",
            "opening_time",
            "closing_time",
        ]
        widgets = {
            "opening_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "closing_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["opening_time"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["closing_time"].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean(self):
        cleaned = super().clean()
        opening = cleaned.get("opening_time")
        closing = cleaned.get("closing_time")
        if opening and closing and closing <= opening:
            raise forms.ValidationError("Closing time must be after opening time.")
        passing = cleaned.get("passing_score")
        if passing is not None and not (0 <= passing <= 100):
            raise forms.ValidationError("Passing score must be between 0 and 100.")
        return cleaned


class QuizUploadForm(forms.Form):
    bank_file = forms.FileField(
        label="Question bank file (.txt or .docx)",
        help_text=(
            "Upload a file containing your question bank and a trailing "
            "answer key. It may contain more questions than the quiz "
            "length -- the system samples randomly per attempt."
        ),
    )


class QuestionReviewForm(forms.Form):
    """One row of the teacher's review/edit page. Options are always
    re-lettered A, B, C... sequentially regardless of the source labels, so
    storage stays contiguous and simple downstream.
    """

    # required=False here because the formset's spare "extra" rows are
    # legitimately blank -- whether that's an error depends on whether the
    # *rest* of the row is also blank, which only clean() can determine.
    question_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}), required=False
    )
    delete = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for letter in OPTION_LETTERS:
            self.fields[f"option_{letter}"] = forms.CharField(
                required=False, label=f"Option {letter}"
            )
        self.fields["correct_label"] = forms.ChoiceField(
            choices=[(letter, letter) for letter in OPTION_LETTERS]
        )

    def clean(self):
        cleaned = super().clean()

        question_text = (cleaned.get("question_text") or "").strip()
        filled = [
            (letter, (cleaned.get(f"option_{letter}") or "").strip())
            for letter in OPTION_LETTERS
        ]
        filled = [(letter, text) for letter, text in filled if text]

        # A spare row nobody touched -- silently skip it rather than
        # erroring, so unused "extra" rows in the formset don't block
        # submission.
        if not question_text and not filled:
            cleaned["_blank"] = True
            return cleaned

        if cleaned.get("delete"):
            return cleaned

        if not question_text:
            raise forms.ValidationError("Question text is required.")
        if len(filled) < 2:
            raise forms.ValidationError("Each question needs at least 2 options.")

        correct = cleaned.get("correct_label")
        if correct not in {letter for letter, _ in filled}:
            raise forms.ValidationError(
                "The correct answer must match one of the filled-in options."
            )

        cleaned["_options"] = [
            {"label": letter, "text": text} for letter, text in filled
        ]
        return cleaned


QuestionReviewFormSet = forms.formset_factory(QuestionReviewForm, extra=2)


def initial_data_for_questions(questions) -> list[dict]:
    """Build formset initial data from parsed ingestion.schemas.QuestionIn
    objects (or plain dicts of the same shape), re-lettering options
    sequentially A, B, C... in their parsed order.
    """
    initial = []
    for q in questions:
        question_text = getattr(q, "question_text", None) or q["question_text"]
        options = getattr(q, "options", None) or q["options"]
        correct_label = getattr(q, "correct_label", None) or q["correct_label"]

        row = {"question_text": question_text}
        new_correct = OPTION_LETTERS[0]
        for i, opt in enumerate(options):
            letter = OPTION_LETTERS[i]
            text = getattr(opt, "text", None) or opt["text"]
            orig_label = getattr(opt, "label", None) or opt["label"]
            row[f"option_{letter}"] = text
            if orig_label == correct_label:
                new_correct = letter
        row["correct_label"] = new_correct
        initial.append(row)
    return initial
