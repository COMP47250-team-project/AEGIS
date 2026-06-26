import uuid
from datetime import datetime

from pydantic import BaseModel


class SessionSummary(BaseModel):
    """One exam session card on the professor dashboard."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    quiz_title: str | None
    course_id: str
    scheduled_start: datetime
    state: str
    student_count: int
    flagged_count: int


class SessionListResponse(BaseModel):
    """Paginated list of session summaries."""

    items: list[SessionSummary]
    total: int
    page: int
    page_size: int


class TimelineEvent(BaseModel):
    """One telemetry event in a student's read-only event timeline."""

    model_config = {"from_attributes": True}

    event_type: str
    payload: dict
    occurred_at: datetime


class TimelineResponse(BaseModel):
    """Paginated, most-recent-first telemetry timeline for one student."""

    student_id: str
    items: list[TimelineEvent]
    total: int
    page: int
    page_size: int
