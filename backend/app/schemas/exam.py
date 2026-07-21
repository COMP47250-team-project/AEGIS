import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

QuestionType = Literal["mcq", "short"]


# ---------------------------------------------------------------------------
# Exam session schemas
# ---------------------------------------------------------------------------

ExamState = Literal["draft", "open", "closed"]
ScoringPreset = Literal["strict", "standard", "lenient"]
# AEGIS-121: closed_book (default, unchanged flow) | open_book (resource panel).
ExamMode = Literal["closed_book", "open_book"]


class ExamCreate(BaseModel):
    quiz_id: uuid.UUID
    course_id: str = Field(..., min_length=1, max_length=255)
    scheduled_start: datetime
    duration_minutes: int = Field(..., gt=0)
    scoring_preset: ScoringPreset = "standard"
    mode: ExamMode = "closed_book"

    @field_validator("scheduled_start")
    @classmethod
    def must_be_future(cls, v: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= now:
            raise ValueError("Please select a future date and time for the exam start.")
        return v


class ExamRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    quiz_id: uuid.UUID
    course_id: str
    scheduled_start: datetime
    duration_minutes: int
    state: ExamState
    scoring_preset: ScoringPreset = "standard"
    mode: ExamMode = "closed_book"
    created_by: str
    opened_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    enrollment_count: int = 0
    quiz_title: str | None = None
    # AEGIS-112b: whether results have been released (drives the professor
    # list's "Evaluate" vs "View Grades" label). has_short_answers is only
    # populated by the exam list endpoint (needs a batch quiz lookup);
    # elsewhere it defaults False, which is harmless since nothing else reads it.
    results_released: bool = False
    has_short_answers: bool = False

    @classmethod
    def from_orm_with_count(
        cls, exam: object, count: int, quiz_title: str | None = None
    ) -> "ExamRead":
        obj = cls.model_validate(exam)
        obj.enrollment_count = count
        obj.quiz_title = quiz_title
        obj.results_released = getattr(exam, "results_released_at", None) is not None
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
    # AEGIS-121: exam mode drives whether the student sees the resource panel.
    mode: ExamMode = "closed_book"


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
    # AEGIS-112c: results are viewable (closed + released, or MCQ-only). Drives
    # the "results ready" notification + the card's View Results action.
    results_ready: bool = False


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
    # AEGIS-118: True when a StudentSession row exists — the student actually
    # joined the exam. False distinguishes "Absent" from "attended but left
    # answers blank" ("No Answer"), which the answers above already show.
    attended: bool = True
    # AEGIS-119: integrity/copy score (0–1) so the grade view can auto-highlight
    # high-risk students. None when scoring hasn't produced a row for them.
    integrity_score: float | None = None


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
    # AEGIS-121: open_book exams show a "Resources accessed" section per student.
    mode: ExamMode = "closed_book"


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


# ---------------------------------------------------------------------------
# Open-book resources (AEGIS-121)
# ---------------------------------------------------------------------------

ResourceType = Literal["url", "file"]


class ResourceCreate(BaseModel):
    """Professor adds a URL resource to an open-book exam's allowlist.

    File resources are created via the multipart upload endpoint, not this
    schema. The URL scheme is restricted to http/https — a ``javascript:`` or
    ``data:`` URL rendered into the student's browser would be a stored-XSS
    vector, since the URL is placed in an <a href>/<iframe src>.
    """

    label: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1)
    # True only when the professor has confirmed the site allows framing;
    # otherwise the student opens it in a new tab (still tracked).
    embed: bool = False

    @field_validator("url")
    @classmethod
    def must_be_http_url(cls, v: str) -> str:
        candidate = v.strip()
        lowered = candidate.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            raise ValueError("Resource URL must start with http:// or https://")
        return candidate


class ResourceRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    exam_id: uuid.UUID
    label: str
    type: ResourceType
    url: str | None = None
    embed: bool = False
    created_at: datetime


class ResourceAccessCreate(BaseModel):
    """Student records opening a resource (durable, via REST).

    ``duration_ms`` is optional: it's absent on the initial open event and
    supplied later (via the duration update) when the student switches away /
    collapses the panel / submits.
    """

    resource_id: uuid.UUID
    duration_ms: int | None = Field(default=None, ge=0)


class ResourceAccessDurationUpdate(BaseModel):
    """Fill in how long a previously-opened resource stayed open."""

    duration_ms: int = Field(..., ge=0)


class ResourceAccessRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    resource_id: uuid.UUID
    opened_at: datetime
    duration_ms: int | None = None


class StudentResourceUsage(BaseModel):
    """Per-student, per-resource aggregate for the professor's grade report."""

    resource_id: uuid.UUID
    label: str
    url: str | None = None
    type: ResourceType
    first_access: datetime
    total_duration_ms: int
    open_count: int


class StudentResourceAccess(BaseModel):
    """All resource usage for one student in an exam, ordered by first access."""

    student_id: str
    student_name: str | None = None
    student_email: str | None = None
    resources: list[StudentResourceUsage]


class ResourceAccessReport(BaseModel):
    """Whole-exam resource-access report (all students)."""

    exam_id: uuid.UUID
    students: list[StudentResourceAccess]
