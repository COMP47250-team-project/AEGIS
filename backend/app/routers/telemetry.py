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

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.exam import Enrollment, ExamSession
from app.models.telemetry import SessionScore
from app.models.user import User
from app.services import telemetry_service
from app.services.scorer import compute_and_save_scores

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

                # Skip pong/ping frames
                if event_data.get("type") in ("ping", "pong"):
                    continue

                try:
                    await telemetry_service.store_event(db, exam_id, student_id, event_data)
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

    try:
        while True:
            # Recompute scores from live telemetry before every broadcast
            try:
                async with AsyncSessionLocal() as db:
                    await compute_and_save_scores(db, exam_id)
            except Exception:
                logger.exception("Live score computation failed for exam %s", exam_id)

            payload = await _build_professor_payload(exam_id)
            try:
                await websocket.send_text(json.dumps(payload))
            except WebSocketDisconnect:
                break

            # Wait 5 seconds, exit early if client disconnects
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                if msg:
                    pass  # Ignore any client message (keepalive)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        logger.info("Professor WS closed: exam=%s professor=%s", exam_id, professor_id)


async def _build_professor_payload(exam_id: uuid.UUID) -> dict:
    """Query current session_scores and enrolled students, return summary."""
    async with AsyncSessionLocal() as db:
        # Load enrolled students
        enrollment_result = await db.execute(
            select(Enrollment).where(Enrollment.exam_id == exam_id)
        )
        enrollments = list(enrollment_result.scalars().all())
        student_ids = [e.student_id for e in enrollments]

        # Load user metadata
        user_map: dict[str, User] = {}
        if student_ids:
            user_result = await db.execute(
                select(User).where(User.id.in_([uuid.UUID(sid) for sid in student_ids]))
            )
            for u in user_result.scalars().all():
                user_map[str(u.id)] = u

        # Load scores (may not exist yet while exam is running)
        score_map: dict[str, SessionScore] = {}
        if student_ids:
            score_result = await db.execute(
                select(SessionScore).where(SessionScore.exam_id == exam_id)
            )
            for s in score_result.scalars().all():
                score_map[s.student_id] = s

        students = []
        for sid in student_ids:
            user = user_map.get(sid)
            score = score_map.get(sid)
            students.append(
                {
                    "student_id": sid,
                    "name": user.full_name if user else None,
                    "email": user.email if user else None,
                    "integrity_score": round(score.integrity_score, 3) if score else None,
                    "tab_switch_score": round(score.tab_switch_score, 3) if score else None,
                    "paste_score": round(score.paste_score, 3) if score else None,
                    "keystroke_score": round(score.keystroke_score, 3) if score else None,
                }
            )

        return {"exam_id": str(exam_id), "students": students}
