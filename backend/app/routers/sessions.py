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
from app.models.exam import Enrollment, ExamSession, StudentSession
from app.models.quiz import Quiz
from app.models.telemetry import SessionScore, TelemetryEvent
from app.models.user import User
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


@router.get("/{session_id}/students/{student_id}/score")
async def get_student_score(
    session_id: uuid.UUID,
    student_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_role("professor")),
) -> dict:
    """Return the integrity score breakdown for one student in a session.

    Returns ``{"available": false}`` when scoring hasn't run yet (exam still open
    or the background job hasn't completed).
    """
    result = await db.execute(
        select(SessionScore).where(
            SessionScore.exam_id == session_id,
            SessionScore.student_id == student_id,
        )
    )
    score = result.scalar_one_or_none()
    if score is None:
        return {"available": False}
    return {
        "available": True,
        "integrity_score": score.integrity_score,
        "has_telemetry": score.has_telemetry,
        "components": {
            "Tab Switch": score.tab_switch_score,
            "Paste": score.paste_score,
            "Keystroke": score.keystroke_score,
            "Focus Loss": score.focus_loss_score,
            "Answer Timing": score.answer_timing_score,
            "Copy Sequence": score.copy_sequence_score,
        },
    }


async def _resolve_student_names(
    db: AsyncSession, student_ids: list[str]
) -> dict[str, str]:
    """Batch-resolve display names for a list of student_id strings.

    Silently skips any id that isn't a valid UUID rather than failing the
    whole lookup.
    """
    valid_ids = [sid for sid in student_ids if _is_valid_uuid(sid)]
    if not valid_ids:
        return {}
    users_result = await db.execute(
        select(User).where(User.id.in_([uuid.UUID(sid) for sid in valid_ids]))
    )
    return {str(u.id): (u.full_name or u.email) for u in users_result.scalars().all()}


def _score_row(
    sid: str, name: str, score: SessionScore | None, attended: bool
) -> dict:
    """Build one /scores row.

    ``attended`` (derived from StudentSession, i.e. the student joined the exam)
    is the source of truth for "Absent" — NOT telemetry presence. A student can
    submit answers via REST without producing telemetry, so keying Absent off
    telemetry wrongly marked submitted students Absent, and could collapse a
    whole cohort to Absent when telemetry didn't flow (AEGIS-119).
    """
    status = "submitted" if attended else "absent"
    if score is None:
        return {
            "student_id": sid,
            "student_name": name,
            "status": status,
            "integrity_score": 0.0,
            "tab_switch_score": 0.0,
            "paste_score": 0.0,
            "keystroke_score": 0.0,
            "focus_loss_score": 0.0,
            "answer_timing_score": 0.0,
            "copy_sequence_score": 0.0,
            "flagged": False,
            "has_telemetry": False,
        }
    return {
        "student_id": sid,
        "student_name": name,
        "status": status,
        "integrity_score": score.integrity_score,
        "tab_switch_score": score.tab_switch_score,
        "paste_score": score.paste_score,
        "keystroke_score": score.keystroke_score,
        "focus_loss_score": score.focus_loss_score,
        "answer_timing_score": score.answer_timing_score,
        "copy_sequence_score": score.copy_sequence_score,
        "flagged": score.integrity_score >= FLAGGED_THRESHOLD,
        "has_telemetry": score.has_telemetry,
    }


@router.get("/{session_id}/scores")
async def list_session_scores(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> list[dict]:
    """Return integrity scores for every enrolled student in a session.

    Enrolled students who produced zero telemetry (e.g. never joined the
    exam) still appear, with a real 0 score and has_telemetry=False, instead
    of being silently omitted (AEGIS-118). Only the exam owner may access
    this endpoint.
    """
    exam = await db.scalar(
        select(ExamSession).where(ExamSession.id == session_id)
    )
    if exam is None or str(exam.created_by) != user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    enrollment_result = await db.execute(
        select(Enrollment.student_id).where(Enrollment.exam_id == session_id)
    )
    enrolled_ids = [row[0] for row in enrollment_result.all()]

    result = await db.execute(
        select(SessionScore).where(SessionScore.exam_id == session_id)
    )
    scores_by_student = {s.student_id: s for s in result.scalars().all()}

    # Attendance = the student created a StudentSession (joined/consented). This,
    # not telemetry, decides "Absent" (AEGIS-119).
    attended_result = await db.execute(
        select(StudentSession.student_id).where(
            StudentSession.exam_id == session_id
        )
    )
    attended_ids = {row[0] for row in attended_result.all()}

    student_ids = list(set(enrolled_ids) | set(scores_by_student.keys()))
    name_map = await _resolve_student_names(db, student_ids)

    items = [
        _score_row(
            sid,
            name_map.get(sid, sid),
            scores_by_student.get(sid),
            sid in attended_ids,
        )
        for sid in student_ids
    ]
    # Absent students last, then by descending integrity score.
    return sorted(
        items,
        key=lambda x: (x["status"] == "absent", -x["integrity_score"]),
    )


def _is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


# AEGIS-104: map each behavioural signal to a triage severity so the professor
# view can highlight the events that matter most.
_EVENT_SEVERITY: dict[str, str] = {
    "paste": "high",
    "tab_blur": "high",
    "key_interval": "medium",
    "resize": "low",
    "first_keypress": "low",
    "tab_return": "info",
    "question_time": "info",
}


def _event_severity(event_type: str) -> str:
    return _EVENT_SEVERITY.get(event_type, "info")


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
            event_type=e.event_type,
            payload=e.payload,
            occurred_at=e.occurred_at,
            severity=_event_severity(e.event_type),
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
