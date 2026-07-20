"""Auto-open and auto-close scheduled exams (AEGIS-104, AEGIS-115).

An exam opens automatically once its scheduled start time passes — the professor
no longer has to trigger it manually. Implemented lazily: any read path a
student hits (dashboard list, session entry, loading questions) opens a due
exam, so a waiting student's dashboard poll opens it on time and the IKI
baseline starts from the real exam start rather than an idle wait.

Auto-close (AEGIS-115): when a student hits a read path and the exam's
duration has elapsed (scheduled_start + duration_minutes <= now), the exam
is transitioned to closed and every connected student is notified over
WebSocket. This mirrors the lazy-open strategy — no background task needed,
the next student poll closes it on time.

Idempotent — only ever transitions draft -> open or open -> closed.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import ExamSession
from app.services.scoring import dispatch_score_job

logger = logging.getLogger(__name__)


def is_due(exam: ExamSession, now: datetime) -> bool:
    """True if a draft exam's scheduled start has passed and it should open."""
    if exam.state != "draft":
        return False
    start = exam.scheduled_start
    if start is None:
        return False
    # scheduled_start may be stored naive — treat it as UTC.
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start <= now


def is_expired(exam: ExamSession, now: datetime) -> bool:
    """True if an open exam's duration has elapsed and it should close.

    Uses scheduled_start + duration_minutes as the authoritative end time,
    matching the end time the frontend CountdownTimer displays to students.
    Returns False if any required field is missing, so a misconfigured exam
    never closes silently.
    """
    if exam.state != "open":
        return False
    start = exam.scheduled_start
    if start is None or exam.duration_minutes is None:
        return False
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=exam.duration_minutes)
    return now >= end


async def auto_open_if_due(db: AsyncSession, exam: ExamSession) -> bool:
    """Open a single exam if its scheduled start has passed (commits). Returns
    True if this call opened it."""
    now = datetime.now(timezone.utc)
    if not is_due(exam, now):
        return False
    exam.state = "open"
    exam.opened_at = now
    await db.commit()
    await db.refresh(exam)
    logger.info("Auto-opened exam %s at its scheduled start", exam.id)
    return True


async def auto_close_if_expired(db: AsyncSession, exam: ExamSession) -> bool:
    """Close a single open exam if its duration has elapsed (AEGIS-115).

    Commits the state change, then broadcasts exam_closed to every connected
    student over WebSocket so they see a clean terminal state instead of a
    stuck Submitting spinner. Returns True if this call closed it.

    Late-imports close_exam_sessions to avoid a module-level import cycle
    with app.routers.telemetry (same pattern as exams.py close endpoint).
    """
    now = datetime.now(timezone.utc)
    if not is_expired(exam, now):
        return False

    exam.state = "closed"
    exam.closed_at = now
    await db.commit()
    await db.refresh(exam)
    logger.info("Auto-closed exam %s — duration elapsed", exam.id)

    # Notify connected students — failure must not block the read path.
    try:
        from app.routers.telemetry import close_exam_sessions
        notified = await close_exam_sessions(str(exam.id))
        logger.info(
            "Auto-close exam %s — notified %d student(s)", exam.id, notified
        )
    except Exception:
        logger.exception(
            "Auto-close exam %s — failed to notify students", exam.id
        )

    # AEGIS-114/118: the manual close endpoint dispatches score computation —
    # this lazy auto-close path must too, or every auto-closed exam's
    # session_scores stays empty forever and every student reads as "Absent"
    # regardless of real telemetry. dispatch_score_job already catches its
    # own exceptions, so a failure here can't break this read path either.
    await dispatch_score_job(exam.id)

    return True


async def auto_open_due(db: AsyncSession, exams: list[ExamSession]) -> None:
    """Open every due exam in a list in a single commit (batch read paths)."""
    now = datetime.now(timezone.utc)
    opened = False
    for exam in exams:
        if is_due(exam, now):
            exam.state = "open"
            exam.opened_at = now
            opened = True
            logger.info("Auto-opened exam %s at its scheduled start", exam.id)
    if opened:
        await db.commit()
