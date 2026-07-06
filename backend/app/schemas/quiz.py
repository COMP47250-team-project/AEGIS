import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Question schemas
# ---------------------------------------------------------------------------


class QuestionCreate(BaseModel):
    type: Literal["mcq", "short"]
    prompt: str = Field(..., min_length=1, max_length=2000)
    options: list[str] | None = None
    correct_answer: str | None = None
    position: int | None = Field(default=None, ge=0)
    max_score: int = Field(default=1, gt=0)

    @model_validator(mode="after")
    def validate_mcq_fields(self) -> "QuestionCreate":
        if self.type == "mcq":
            if not self.options or len(self.options) < 2:
                raise ValueError("MCQ questions require at least 2 options")
            if not self.correct_answer:
                raise ValueError("MCQ questions require a correct_answer")
        return self


class QuestionUpdate(BaseModel):
    type: Literal["mcq", "short"] | None = None
    prompt: str | None = Field(default=None, min_length=1, max_length=2000)
    options: list[str] | None = None
    correct_answer: str | None = None
    position: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_mcq_fields(self) -> "QuestionUpdate":
        # Only validate when type is being explicitly set to mcq
        if self.type == "mcq":
            if self.options is not None and len(self.options) < 2:
                raise ValueError("MCQ questions require at least 2 options")
        return self


class QuestionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    quiz_id: uuid.UUID
    type: str
    prompt: str
    options: list[str] | None
    correct_answer: str | None
    position: int
    max_score: int


# ---------------------------------------------------------------------------
# Question bank (AEGIS-90) — reuse questions from a professor's past quizzes
# ---------------------------------------------------------------------------


class QuestionBankItem(BaseModel):
    question_id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_title: str
    question_text: str
    question_type: str
    options: list[str] | None
    correct_answer: str | None
    # Questions have no own timestamp; this is the parent quiz's creation time.
    created_at: datetime


class QuestionBankResponse(BaseModel):
    items: list[QuestionBankItem]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Quiz schemas
# ---------------------------------------------------------------------------


class QuizCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    duration_minutes: int = Field(..., gt=0)


class QuizRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str
    description: str | None
    duration_minutes: int
    is_published: bool
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    questions: list[QuestionRead] = []
