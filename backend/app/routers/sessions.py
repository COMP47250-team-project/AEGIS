"""Professor session dashboard (AEGIS-58).

GET /sessions?status=active — paginated list of the professor's exam sessions
with per-session student and flagged-student counts, for the dashboard cards.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.exam import Enrollment, ExamSession
from app.models.quiz import Quiz
from app.models.telemetry import SessionScore, TelemetryEvent
from app.schemas.session import (
    SessionListResponse,
    SessionSummary,
    TimelineEvent,
    TimelineResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

# A student is "flagged" when their integrity score reaches this threshold.
# Matches the professor UI's existing "High risk" cutoff (0.7).
FLAGGED_THRESHOLD = 0.7

# Dashboard "status" filter → exam state-machine value.
_STATUS_TO_STATE = {"active": "open", "completed": "closed", "draft": "draft"}


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
    status: Literal["active", "completed", "draft", "all"] = Query("active"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SessionListResponse:
    base = select(ExamSession).where(ExamSession.created_by == user_id)
    if status != "all":
        base = base.where(ExamSession.state == _STATUS_TO_STATE[status])

    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0

    result = await db.execute(
        base.order_by(ExamSession.scheduled_start.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    sessions = list(result.scalars().all())

    items: list[SessionSummary] = []
    for s in sessions:
        student_count = (
            await db.scalar(
                select(func.count())
                .select_from(Enrollment)
                .where(Enrollment.exam_id == s.id)
            )
            or 0
        )
        flagged_count = (
            await db.scalar(
                select(func.count())
                .select_from(SessionScore)
                .where(
                    SessionScore.exam_id == s.id,
                    SessionScore.integrity_score >= FLAGGED_THRESHOLD,
                )
            )
            or 0
        )
        quiz_title = await db.scalar(select(Quiz.title).where(Quiz.id == s.quiz_id))
        items.append(
            SessionSummary(
                id=s.id,
                quiz_title=quiz_title,
                course_id=s.course_id,
                scheduled_start=s.scheduled_start,
                state=s.state,
                student_count=student_count,
                flagged_count=flagged_count,
            )
        )

    return SessionListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get(
    "/{session_id}/students/{student_id}/events",
    response_model=TimelineResponse,
)
async def student_event_timeline(
    session_id: uuid.UUID,
    student_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> TimelineResponse:
    """Read-only, most-recent-first telemetry timeline for one student in a
    session. Only the exam owner may view it."""
    owner = await db.scalar(
        select(ExamSession.created_by).where(ExamSession.id == session_id)
    )
    if owner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if owner != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your exam session")

    base = select(TelemetryEvent).where(
        TelemetryEvent.exam_id == session_id,
        TelemetryEvent.student_id == student_id,
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    result = await db.execute(
        base.order_by(TelemetryEvent.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        TimelineEvent(
            event_type=e.event_type, payload=e.payload, occurred_at=e.occurred_at
        )
        for e in result.scalars().all()
    ]
    return TimelineResponse(
        student_id=student_id,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
