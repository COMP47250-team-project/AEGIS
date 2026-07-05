"""Auto-open scheduled exams (AEGIS-104).

An exam opens automatically once its scheduled start time passes — the professor
no longer has to trigger it manually. Implemented lazily: any read path a
student hits (dashboard list, session entry, loading questions) opens a due
exam, so a waiting student's dashboard poll opens it on time and the IKI
baseline starts from the real exam start rather than an idle wait.

Idempotent — only ever transitions draft -> open. A future enhancement could add
a background sweep so exams open even when nobody is looking; lazy open already
covers "students can begin on time".
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import ExamSession

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
