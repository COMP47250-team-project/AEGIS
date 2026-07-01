"""CSV export API for session results.

GET /api/sessions/{exam_id}/export

Auth: professor role only (verified via JWT + exam ownership).
Returns a StreamingResponse so rows are yielded one at a time — no full
result set is loaded into memory regardless of student count.
Encoding: UTF-8 with BOM so Excel opens it correctly without an import wizard.
"""
import csv
import io
import uuid
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from sqlalchemy import select
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal, get_db
from app.models.exam import Enrollment, ExamSession
from app.models.risk import RiskFlag
from app.models.telemetry import SessionScore, TelemetryEvent
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["export"])

_bearer = HTTPBearer()

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


# ── Streaming row generator ───────────────────────────────────────────────────

async def _csv_row_generator(
    exam_id: uuid.UUID,
    exam: ExamSession,
) -> AsyncIterator[bytes]:
    """
    Yield CSV bytes one row at a time.

    Strategy:
      1. Yield UTF-8 BOM + header row immediately.
      2. Open a single DB session and stream enrollments in batches of 50
         using offset pagination — never holds the full result set in memory.
      3. For each student, fetch their score, flag, and telemetry counts
         with targeted single-row queries (indexed lookups, not table scans).
      4. Yield each data row as encoded bytes before moving to the next student.

    exam_duration_seconds is computed from exam.opened_at → exam.closed_at.
    If either timestamp is missing (exam never opened/closed properly) the
    cell is left blank rather than raising.
    """
    # Compute exam duration once — same for every row
    if exam.opened_at and exam.closed_at:
        exam_duration_seconds = int(
            (exam.closed_at - exam.opened_at).total_seconds()
        )
    else:
        exam_duration_seconds = ""

    # BOM + header
    buf = io.StringIO()
    writer = csv.writer(buf)
    buf.write("\ufeff")  # UTF-8 BOM for Excel
    writer.writerow(_HEADERS)
    yield buf.getvalue().encode("utf-8")

    # Stream students in pages of 50 — constant memory regardless of cohort size
    PAGE = 50
    offset = 0

    while True:
        enrollment_result = await db.execute(
            select(Enrollment, User)
            .join(User, User.id == Enrollment.student_id.cast(uuid.UUID), isouter=True)
            .where(Enrollment.exam_id == exam_id)
            .order_by(Enrollment.enrolled_at)
            .limit(PAGE)
            .offset(offset)
        )
        rows = enrollment_result.all()
        if not rows:
            break

        for enrollment, user in rows:
            student_id_str = enrollment.student_id

            score_result = await db.execute(
                select(SessionScore).where(
                    SessionScore.exam_id == exam_id,
                    SessionScore.student_id == student_id_str,
                )
            )
            score = score_result.scalar_one_or_none()

            flag_result = await db.execute(
                select(RiskFlag).where(
                    RiskFlag.exam_id == exam_id,
                    RiskFlag.student_id == student_id_str,
                )
            )
            flag = flag_result.scalar_one_or_none()

            tab_blur_result = await db.execute(
                select(TelemetryEvent).where(
                    TelemetryEvent.exam_id == exam_id,
                    TelemetryEvent.student_id == student_id_str,
                    TelemetryEvent.event_type.in_(["tab_blur", "tab_hidden"]),
                )
            )
            tab_blur_count = len(tab_blur_result.scalars().all())

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
) -> StreamingResponse:
    """
    Stream session results for exam_id as a UTF-8 CSV file.

    - Auth: Bearer JWT with role=professor.
    - Ownership: professor must be the exam creator.
    - Memory: rows are yielded one at a time; no full result set in memory.
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

    filename = f"session_{exam_id}.csv"
    return StreamingResponse(
        _csv_row_generator(exam_id, exam),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )
