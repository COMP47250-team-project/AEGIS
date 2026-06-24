"""WebSocket telemetry gateway.

Two endpoints:
  /ws/exam/{exam_id}       — Student sends raw telemetry events during an exam.
  /ws/professor/{exam_id}  — Professor receives per-student risk summaries every 5s.

Both validate the JWT from the ?token= query parameter.
Telemetry is independent of answer submission: a WS failure never affects exam completion.
"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.exam import Enrollment, ExamSession
from app.models.user import User
from app.services import telemetry_service
from app.services.live_monitor import live_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["telemetry"])


def _decode_token(token: str) -> str | None:
    """Return user_id from a valid JWT or None."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload.get("sub")
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Student WebSocket — receives telemetry events from the browser SDK
# ---------------------------------------------------------------------------


@router.websocket("/exam/{exam_id}")
async def exam_telemetry_ws(
    websocket: WebSocket,
    exam_id: uuid.UUID,
    token: str = Query(...),
) -> None:
    """Accept a student's telemetry stream for the duration of their exam.

    The client sends JSON frames matching the TelemetryEvent schema.
    Each frame is validated and stored. Invalid frames are silently dropped.
    """
    student_id = _decode_token(token)
    if student_id is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    logger.info("Telemetry WS opened: exam=%s student=%s", exam_id, student_id)

    try:
        async with AsyncSessionLocal() as db:
            # Resolve the display name + email once for the live monitor.
            student_name, student_email = await _lookup_identity(db, student_id)

            while True:
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await websocket.send_text('{"type":"ping"}')
                    continue

                try:
                    event_data: dict[str, object] = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                event_type = event_data.get("type")
                # Skip pong/ping frames
                if event_type in ("ping", "pong"):
                    continue

                # Feed the live view (in-memory, never blocks the student).
                if isinstance(event_type, str):
                    payload = event_data.get("payload")
                    live_monitor.record_event(
                        str(exam_id),
                        student_id,
                        event_type,
                        payload if isinstance(payload, dict) else {},
                        name=student_name,
                        email=student_email,
                    )

                try:
                    await telemetry_service.store_event(
                        db, exam_id, student_id, event_data
                    )
                except Exception:
                    logger.exception("Failed to store telemetry event")

    except WebSocketDisconnect:
        logger.info("Telemetry WS closed: exam=%s student=%s", exam_id, student_id)


# ---------------------------------------------------------------------------
# Professor WebSocket — broadcasts per-student risk summaries every 5 seconds
# ---------------------------------------------------------------------------


@router.websocket("/professor/{exam_id}")
async def professor_monitor_ws(
    websocket: WebSocket,
    exam_id: uuid.UUID,
    token: str = Query(...),
) -> None:
    """Push per-student integrity summaries to the professor every 5 seconds.

    The professor must be the exam owner; the role check is implicit via
    the exam's created_by field.
    """
    professor_id = _decode_token(token)
    if professor_id is None:
        await websocket.close(code=1008)
        return

    # Verify professor owns this exam
    async with AsyncSessionLocal() as db:
        exam_result = await db.execute(
            select(ExamSession).where(ExamSession.id == exam_id)
        )
        exam = exam_result.scalar_one_or_none()
        if exam is None or exam.created_by != professor_id:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    logger.info("Professor WS opened: exam=%s professor=%s", exam_id, professor_id)

    # One-time DB read so enrolled students show up (inactive) before they send
    # anything; every tick after this is a pure in-memory snapshot.
    try:
        async with AsyncSessionLocal() as db:
            await _seed_roster(db, exam_id)
    except Exception:
        logger.exception("Failed to seed roster for exam %s", exam_id)

    try:
        while True:
            payload = live_monitor.snapshot(str(exam_id))
            try:
                await websocket.send_text(json.dumps(payload))
            except WebSocketDisconnect:
                break

            # Wait 5 seconds, exit early if the professor disconnects.
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        logger.info("Professor WS closed: exam=%s professor=%s", exam_id, professor_id)


async def _lookup_identity(
    db: AsyncSession, student_id: str
) -> tuple[str | None, str | None]:
    """Return a student's (display name, email), or (None, None) if not found / bad id."""
    try:
        sid = uuid.UUID(student_id)
    except ValueError:
        return None, None
    result = await db.execute(select(User).where(User.id == sid))
    user = result.scalar_one_or_none()
    if user is None:
        return None, None
    return user.full_name, user.email


async def _seed_roster(db: AsyncSession, exam_id: uuid.UUID) -> None:
    """Register all enrolled students (with names) so they appear in the view."""
    enrollment_result = await db.execute(
        select(Enrollment).where(Enrollment.exam_id == exam_id)
    )
    student_ids = [e.student_id for e in enrollment_result.scalars().all()]
    if not student_ids:
        return

    identity_by_id: dict[str, tuple[str | None, str | None]] = {}
    user_result = await db.execute(
        select(User).where(User.id.in_([uuid.UUID(sid) for sid in student_ids]))
    )
    for u in user_result.scalars().all():
        identity_by_id[str(u.id)] = (u.full_name, u.email)

    for sid in student_ids:
        name, email = identity_by_id.get(sid, (None, None))
        live_monitor.seed_student(str(exam_id), sid, name, email)
