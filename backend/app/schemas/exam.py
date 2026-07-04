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


class AnswerItemRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    exam_id: uuid.UUID
    student_id: str
    question_id: uuid.UUID
    answer: str
    saved_at: datetime


class AnswerSubmitResponse(BaseModel):
    saved: int
    answers: list[AnswerItemRead]


# ---------------------------------------------------------------------------
# Student session / consent schemas
# ---------------------------------------------------------------------------


class StudentSessionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    exam_id: uuid.UUID
    student_id: str
    consent_at: datetime | None


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

ExamStatusForStudent = Literal["open", "upcoming", "completed"]


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


class StudentExamResults(BaseModel):
    exam_id: uuid.UUID
    exam_title: str
    course_name: str
    closed_at: datetime | None
    mcq_correct: int
    mcq_total: int
    questions: list[StudentAnswerResult]


# ---------------------------------------------------------------------------
# Professor grade report
# ---------------------------------------------------------------------------


class GradeAnswerItem(BaseModel):
    question_id: uuid.UUID
    position: int
    question_type: QuestionType
    prompt: str
    student_answer: str
    correct_answer: str | None
    is_correct: bool | None  # None for short-answer


class StudentGradeEntry(BaseModel):
    student_id: str
    student_email: str | None
    student_name: str | None
    mcq_correct: int
    mcq_total: int
    answers: list[GradeAnswerItem]


class ExamGradeReport(BaseModel):
    exam_id: uuid.UUID
    quiz_title: str
    course_id: str
    mcq_total: int
    short_total: int
    students: list[StudentGradeEntry]


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
