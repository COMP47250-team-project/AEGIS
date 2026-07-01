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
from typing import AsyncIterator

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


# ── Auth helper ───────────────────────────────────────────────────────────────

def _decode_token(token: str) -> dict | None:
    """Decode JWT and return payload dict, or None on any failure."""
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None


async def _require_professor(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Dependency — returns professor user_id or raises 401/403."""
    payload = _decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )
    role = payload.get("role", "")
    if role != "professor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professor role required.",
        )
    user_id: str = payload.get("sub", "")
    return user_id


# ── Streaming row generator ───────────────────────────────────────────────────

async def _csv_row_generator(
    exam_id: uuid.UUID,
    exam: ExamSession,
    db: AsyncSession,
) -> AsyncIterator[bytes]:
    """
    Yield CSV bytes one row at a time using the injected session.

    Paginates enrollments in pages of 50 — constant memory regardless of
    cohort size. User identity is resolved via a separate query per page
    rather than a JOIN so it works on both SQLite (tests) and PostgreSQL
    (production) without dialect-specific casting.
    """
    if exam.opened_at and exam.closed_at:
        exam_duration_seconds: int | str = int(
            (exam.closed_at - exam.opened_at).total_seconds()
        )
    else:
        exam_duration_seconds = ""

    # BOM + header row
    buf = io.StringIO()
    writer = csv.writer(buf)
    buf.write("\ufeff")  # UTF-8 BOM — required for Excel auto-detection
    writer.writerow(_HEADERS)
    yield buf.getvalue().encode("utf-8")

    PAGE = 50
    offset = 0

    while True:
        # Fetch one page of enrollments
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

        # Resolve user identities for this page in one query
        # Store as strings to match Enrollment.student_id type (String(255))
        student_id_strs = [e.student_id for e in enrollments]
        try:
            student_uuids = [uuid.UUID(sid) for sid in student_id_strs]
            user_result = await db.execute(
                select(User).where(User.id.in_(student_uuids))
            )
            users_by_id: dict[str, User] = {
                str(u.id): u for u in user_result.scalars().all()
            }
        except (ValueError, Exception):
            # If any student_id is not a valid UUID, skip user resolution
            users_by_id = {}

        for enrollment in enrollments:
            student_id_str = enrollment.student_id
            user = users_by_id.get(student_id_str)

            # Score (single indexed lookup)
            score_result = await db.execute(
                select(SessionScore).where(
                    SessionScore.exam_id == exam_id,
                    SessionScore.student_id == student_id_str,
                )
            )
            score = score_result.scalar_one_or_none()

            # Risk flag (single indexed lookup)
            flag_result = await db.execute(
                select(RiskFlag).where(
                    RiskFlag.exam_id == exam_id,
                    RiskFlag.student_id == student_id_str,
                )
            )
            flag = flag_result.scalar_one_or_none()

            # Tab blur count
            tab_result = await db.execute(
                select(TelemetryEvent).where(
                    TelemetryEvent.exam_id == exam_id,
                    TelemetryEvent.student_id == student_id_str,
                    TelemetryEvent.event_type.in_(["tab_blur", "tab_hidden"]),
                )
            )
            tab_blur_count = len(tab_result.scalars().all())

            # Paste count
            paste_result = await db.execute(
                select(TelemetryEvent).where(
                    TelemetryEvent.exam_id == exam_id,
                    TelemetryEvent.student_id == student_id_str,
                    TelemetryEvent.event_type == "paste",
                )
            )
            paste_count = len(paste_result.scalars().all())

            buf = io.StringIO()
            writer = csv.writer(buf)
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
                exam_duration_seconds,
            ])
            yield buf.getvalue().encode("utf-8")

        offset += PAGE


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/{exam_id}/export",
    summary="Export session results as CSV",
    response_class=StreamingResponse,
)
async def export_session_csv(
    exam_id: uuid.UUID,
    professor_id: str = Depends(_require_professor),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Stream session results for exam_id as a UTF-8 CSV file.

    - Auth: Bearer JWT with role=professor.
    - Ownership: professor must be the exam creator.
    - Memory: rows are yielded one at a time via an async generator.
    - Filename: session_{exam_id}.csv

    The injected `db` session is passed into the generator so the test
    fixture's dependency override applies throughout the full response stream.
    FastAPI keeps the dependency alive until the response is fully sent, so
    the session remains valid for the entire streaming lifetime.
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

    filename = f"session_{exam_id}.csv"
    return StreamingResponse(
        _csv_row_generator(exam_id, exam, db),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )
