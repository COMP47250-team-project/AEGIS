import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Exam session schemas
# ---------------------------------------------------------------------------

ExamState = Literal["draft", "open", "closed"]


class ExamCreate(BaseModel):
    quiz_id: uuid.UUID
    course_id: str = Field(..., min_length=1, max_length=255)
    scheduled_start: datetime
    duration_minutes: int = Field(..., gt=0)


class ExamRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    quiz_id: uuid.UUID
    course_id: str
    scheduled_start: datetime
    duration_minutes: int
    state: ExamState
    created_by: str
    opened_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    enrollment_count: int = 0

    @classmethod
    def from_orm_with_count(cls, exam: object, count: int) -> "ExamRead":
        obj = cls.model_validate(exam)
        obj.enrollment_count = count
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
# Enrollment schemas
# ---------------------------------------------------------------------------

class EnrollmentCreate(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=255)


class EnrollmentRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    exam_id: uuid.UUID
    student_id: str
    enrolled_at: datetime
