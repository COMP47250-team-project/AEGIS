"""CSV export API for session results.

GET /api/sessions/{exam_id}/export

Auth: professor role only (verified via JWT + exam ownership).
Returns a StreamingResponse so rows are yielded one at a time — no full
result set is loaded into memory regardless of student count.
Encoding: UTF-8 with BOM so Excel opens it correctly without an import wizard.
"""
import csv
import io
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.exam import Enrollment, ExamSession
from app.models.risk import RiskFlag
from app.models.telemetry import SessionScore, TelemetryEvent
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["export"])

_bearer = HTTPBearer()

# ── CSV column definitions ────────────────────────────────────────────────────

_HEADERS = [
    "student_id",
    "name",
    "student_number",
    "risk_score",
    "tab_blur_count",
    "paste_count",
    "iki_score",
    "first_keypress_score",
    "answer_time_score",
    "resize_score",
    "flagged",
    "exam_duration_seconds",
]

# ── Auth ──────────────────────────────────────────────────────────────────────


def _decode_token(token: str) -> dict | None:
    """Decode JWT and return payload dict, or None on any failure."""
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None


# Sonar: sync function — async keyword removed as there are no awaits
def _require_professor(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Dependency — returns professor user_id or raises 401/403."""
    payload = _decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )
    if payload.get("role", "") != "professor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professor role required.",
        )
    return payload.get("sub", "")


# Annotated dependency aliases — satisfies Sonar "Use Annotated type hints" warning
ProfessorDep = Annotated[str, Depends(_require_professor)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


# ── Per-student data fetchers (extracted to reduce cognitive complexity) ──────


async def _fetch_score(
    db: AsyncSession, exam_id: uuid.UUID, student_id: str
) -> SessionScore | None:
    result = await db.execute(
        select(SessionScore).where(
            SessionScore.exam_id == exam_id,
            SessionScore.student_id == student_id,
        )
    )
    return result.scalar_one_or_none()


async def _fetch_flag(
    db: AsyncSession, exam_id: uuid.UUID, student_id: str
) -> RiskFlag | None:
    result = await db.execute(
        select(RiskFlag).where(
            RiskFlag.exam_id == exam_id,
            RiskFlag.student_id == student_id,
        )
    )
    return result.scalar_one_or_none()


async def _fetch_event_count(
    db: AsyncSession,
    exam_id: uuid.UUID,
    student_id: str,
    event_types: list[str],
) -> int:
    result = await db.execute(
        select(TelemetryEvent).where(
            TelemetryEvent.exam_id == exam_id,
            TelemetryEvent.student_id == student_id,
            TelemetryEvent.event_type.in_(event_types),
        )
    )
    return len(result.scalars().all())


async def _resolve_users(
    db: AsyncSession, student_id_strs: list[str]
) -> dict[str, User]:
    """Batch-resolve User rows for a list of student_id strings."""
    try:
        uuids = [uuid.UUID(sid) for sid in student_id_strs]
    except ValueError:
        return {}
    result = await db.execute(select(User).where(User.id.in_(uuids)))
    return {str(u.id): u for u in result.scalars().all()}


def _exam_duration(exam: ExamSession) -> int | str:
    """Return exam duration in seconds, or empty string if timestamps missing."""
    if exam.opened_at and exam.closed_at:
        return int((exam.closed_at - exam.opened_at).total_seconds())
    return ""


def _build_csv_row(
    writer: Any,
    buf: io.StringIO,
    student_id_str: str,
    user: User | None,
    score: SessionScore | None,
    flag: RiskFlag | None,
    tab_blur_count: int,
    paste_count: int,
    exam_duration: int | str,
) -> bytes:
    """Serialise one student's data to a CSV row and return encoded bytes."""
    buf.seek(0)
    buf.truncate()
    writer.writerow([
        student_id_str,
        user.full_name if user else "",
        str(user.id) if user else student_id_str,
        round(score.integrity_score, 4) if score else "",
        tab_blur_count,
        paste_count,
        round(score.keystroke_score, 4) if score else "",
        round(score.focus_loss_score, 4) if score else "",
        round(score.answer_timing_score, 4) if score else "",
        round(score.copy_sequence_score, 4) if score else "",
        "YES" if flag else "NO",
        exam_duration,
    ])
    return buf.getvalue().encode("utf-8")


# ── Streaming row generator ───────────────────────────────────────────────────


async def _csv_row_generator(
    exam_id: uuid.UUID,
    exam: ExamSession,
    db: AsyncSession,
) -> AsyncIterator[bytes]:
    """
    Yield CSV bytes one row at a time using the injected session.

    Paginates enrollments in pages of 50 — constant memory regardless of
    cohort size. Cognitive complexity kept low by delegating each concern
    to a dedicated helper function.
    """
    exam_duration = _exam_duration(exam)

    # BOM + header
    buf = io.StringIO()
    writer = csv.writer(buf)
    buf.write("\ufeff")  # UTF-8 BOM — required for Excel auto-detection
    writer.writerow(_HEADERS)
    yield buf.getvalue().encode("utf-8")

    PAGE = 50
    offset = 0

    while True:
        enrollment_result = await db.execute(
            select(Enrollment)
            .where(Enrollment.exam_id == exam_id)
            .order_by(Enrollment.enrolled_at)
            .limit(PAGE)
            .offset(offset)
        )
        enrollments = enrollment_result.scalars().all()
        if not enrollments:
            break

        users_by_id = await _resolve_users(
            db, [e.student_id for e in enrollments]
        )

        for enrollment in enrollments:
            sid = enrollment.student_id
            score = await _fetch_score(db, exam_id, sid)
            flag = await _fetch_flag(db, exam_id, sid)
            tab_blur_count = await _fetch_event_count(
                db, exam_id, sid, ["tab_blur", "tab_hidden"]
            )
            paste_count = await _fetch_event_count(db, exam_id, sid, ["paste"])

            # Reuse the same buffer across rows — seek/truncate is cheaper
            # than allocating a new StringIO per student
            yield _build_csv_row(
                writer,
                buf,
                sid,
                users_by_id.get(sid),
                score,
                flag,
                tab_blur_count,
                paste_count,
                exam_duration,
            )

        offset += PAGE


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.get(
    "/{exam_id}/export",
    summary="Export session results as CSV",
    response_class=StreamingResponse,
)
async def export_session_csv(
    exam_id: uuid.UUID,
    professor_id: ProfessorDep,
    db: DbDep,
) -> StreamingResponse:
    """
    Stream session results for exam_id as a UTF-8 CSV file.

    - Auth: Bearer JWT with role=professor.
    - Ownership: professor must be the exam creator.
    - Memory: rows are yielded one at a time via an async generator.
    - Filename: session_{exam_id}.csv
    """
    exam_result = await db.execute(
        select(ExamSession).where(ExamSession.id == exam_id)
    )
    exam = exam_result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam session {exam_id} not found.",
        )
    if exam.created_by != professor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this exam session.",
        )

    return StreamingResponse(
        _csv_row_generator(exam_id, exam, db),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=session_{exam_id}.csv",
        },
    )
