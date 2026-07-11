import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QuestionType = Literal["mcq", "short"]


# ---------------------------------------------------------------------------
# Exam session schemas
# ---------------------------------------------------------------------------

ExamState = Literal["draft", "open", "closed"]
ScoringPreset = Literal["strict", "standard", "lenient"]


class ExamCreate(BaseModel):
    quiz_id: uuid.UUID
    course_id: str = Field(..., min_length=1, max_length=255)
    scheduled_start: datetime
    duration_minutes: int = Field(..., gt=0)
    scoring_preset: ScoringPreset = "standard"


class ExamRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    quiz_id: uuid.UUID
    course_id: str
    scheduled_start: datetime
    duration_minutes: int
    state: ExamState
    scoring_preset: ScoringPreset = "standard"
    created_by: str
    opened_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    enrollment_count: int = 0
    quiz_title: str | None = None

    @classmethod
    def from_orm_with_count(
        cls, exam: object, count: int, quiz_title: str | None = None
    ) -> "ExamRead":
        obj = cls.model_validate(exam)
        obj.enrollment_count = count
        obj.quiz_title = quiz_title
        return obj


# ---------------------------------------------------------------------------
# Answer submission schemas
# ---------------------------------------------------------------------------


class AnswerItem(BaseModel):
    question_id: uuid.UUID
    answer: str = Field(default="")


class AnswerSubmit(BaseModel):
    answers: list[AnswerItem] = Field(..., min_length=1)
    # AEGIS-111: true when the student clicks "Finish Exam" — finalises the
    # submission so the exam can't be re-entered or re-submitted.
    final: bool = False


class AnswerItemRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    exam_id: uuid.UUID
    student_id: str
    question_id: uuid.UUID
    answer: str
    saved_at: datetime
    manual_score: float | None = None


class AnswerSubmitResponse(BaseModel):
    saved: int
    answers: list[AnswerItemRead]
    # AEGIS-111: set once the exam is finalised (final=true submit).
    submitted_at: datetime | None = None


# ---------------------------------------------------------------------------
# Student session / consent schemas
# ---------------------------------------------------------------------------


class StudentSessionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    exam_id: uuid.UUID
    student_id: str
    consent_at: datetime | None
    # AEGIS-111: when set, the exam is complete and the student can't re-enter.
    submitted_at: datetime | None = None
    exam_state: str = "open"


# ---------------------------------------------------------------------------
# Student-facing question schema (correct_answer intentionally excluded)
# ---------------------------------------------------------------------------


class QuestionForStudent(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    type: QuestionType
    prompt: str
    options: list[str] | None
    position: int


# ---------------------------------------------------------------------------
# Student dashboard — list of enrolled exam sessions
# ---------------------------------------------------------------------------

ExamStatusForStudent = Literal["open", "upcoming", "completed", "submitted"]


class StudentExamListItem(BaseModel):
    exam_id: uuid.UUID
    exam_title: str
    course_name: str
    status: ExamStatusForStudent
    starts_at: datetime
    ends_at: datetime


# ---------------------------------------------------------------------------
# Student exam results (after exam is closed)
# ---------------------------------------------------------------------------


class StudentAnswerResult(BaseModel):
    question_id: uuid.UUID
    position: int
    question_type: QuestionType
    prompt: str
    options: list[str] | None
    student_answer: str
    correct_answer: str | None  # revealed for MCQ after closing
    is_correct: bool | None  # None for short-answer (manual grading)
    # AEGIS-112: the professor's manual score for a short answer (once graded).
    manual_score: float | None = None
    max_score: int = 1


class StudentExamResults(BaseModel):
    exam_id: uuid.UUID
    exam_title: str
    course_name: str
    closed_at: datetime | None
    mcq_correct: int
    mcq_total: int
    questions: list[StudentAnswerResult]
    integrity_score: float | None = None
    # AEGIS-112: overall points (MCQ + manually graded short answers).
    points_earned: float = 0.0
    points_possible: int = 0
    # False while any short answer is still awaiting a manual grade.
    fully_graded: bool = True
    # AEGIS-112b: false while a manually-graded exam is still "Under Review"
    # (professor hasn't clicked Submit Grades). MCQ-only exams are always true.
    results_released: bool = True


# ---------------------------------------------------------------------------
# Professor grade report
# ---------------------------------------------------------------------------


class GradeAnswerItem(BaseModel):
    question_id: uuid.UUID
    answer_id: uuid.UUID | None = None
    position: int
    question_type: QuestionType
    prompt: str
    student_answer: str
    correct_answer: str | None
    is_correct: bool | None  # None for short-answer
    manual_score: float | None = None
    max_score: int = 1


class StudentGradeEntry(BaseModel):
    student_id: str
    student_email: str | None
    student_name: str | None
    mcq_correct: int
    mcq_total: int
    answers: list[GradeAnswerItem]


class ManualGradeSubmit(BaseModel):
    answer_id: uuid.UUID
    score: float = Field(..., ge=0)


class ExamGradeReport(BaseModel):
    exam_id: uuid.UUID
    quiz_title: str
    course_id: str
    mcq_total: int
    short_total: int
    students: list[StudentGradeEntry]
    # AEGIS-112b: have results been released to students, and how many short
    # answers still need a manual grade before release.
    results_released: bool = False
    ungraded_short: int = 0


# ---------------------------------------------------------------------------
# Enrollment schemas
# ---------------------------------------------------------------------------


class EnrollmentCreate(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=255)


class EnrollmentByEmail(BaseModel):
    email: str = Field(..., min_length=1)


class EnrollmentRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    exam_id: uuid.UUID
    student_id: str
    enrolled_at: datetime
