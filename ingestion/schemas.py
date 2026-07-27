from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError, field_validator, model_validator


class OptionIn(BaseModel):
    label: str
    text: str


class QuestionIn(BaseModel):
    question_number: int | None = None
    question_text: str
    options: list[OptionIn]
    correct_label: str

    @field_validator("question_text")
    @classmethod
    def validate_question_text(cls, v):
        if not v or not v.strip():
            raise ValueError("question_text must not be empty")
        return v.strip()

    @field_validator("options")
    @classmethod
    def validate_option_count(cls, v):
        if not (2 <= len(v) <= 6):
            raise ValueError("each question needs 2-6 options")
        return v

    @model_validator(mode="after")
    def validate_correct_label(self):
        labels = {opt.label.strip().upper() for opt in self.options}
        if self.correct_label.strip().upper() not in labels:
            raise ValueError(
                f"correct_label {self.correct_label!r} does not match any "
                f"option label {sorted(labels)}"
            )
        return self


@dataclass
class RowError:
    index: int
    raw: dict
    message: str


@dataclass
class IngestionResult:
    questions: list[QuestionIn] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


def validate_rows(raw_rows: list[dict]) -> IngestionResult:
    """Validate each parsed row independently so one malformed question
    doesn't sink the whole batch -- offending rows are surfaced separately
    (for the teacher's review page to flag as "fill in manually").
    """
    result = IngestionResult()
    for i, row in enumerate(raw_rows):
        try:
            question = QuestionIn.model_validate(row)
        except ValidationError as exc:
            result.errors.append(RowError(index=i, raw=row, message=str(exc)))
        else:
            result.questions.append(question)
    return result
