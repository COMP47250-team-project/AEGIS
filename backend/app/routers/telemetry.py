"""WebSocket telemetry gateway.

Two endpoints:
  /ws/exam/{exam_id}       — Student sends raw telemetry events during an exam.
  /ws/professor/{exam_id}  — Professor receives per-student risk summaries every 5s.

Both validate the JWT from the ?token= query parameter.
Telemetry is independent of answer submission: a WS failure never affects exam completion.

Close codes used by the student endpoint:
  4401 — JWT missing, expired, or invalid.
  4403 — Student is not enrolled in the requested exam.
"""

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from app.models.exam import Enrollment, ExamSession, StudentSession
from app.config import settings
from app.database import AsyncSessionLocal
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services import telemetry_service
from app.services.live_monitor import live_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["telemetry"])

# In-memory registry: {exam_id_str: {student_id: WebSocket}}
# Shared across all coroutines in the process; guarded by _registry_lock.
_connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)
_registry_lock = asyncio.Lock()

# WebSocket close codes (application-level, 4000-4999)
_WS_UNAUTHORIZED = 4401
_WS_FORBIDDEN = 4403

# Heartbeat interval expected by the AEGIS-48 acceptance criteria
_HEARTBEAT_INTERVAL_S = 30


def _decode_token(token: str) -> str | None:
    """Return user_id from a valid JWT or None."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload.get("sub")
    except JWTError:
        return None


async def _is_enrolled(exam_id: uuid.UUID, student_id: str) -> bool:
    """Return True if the student has an enrollment row for this exam."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Enrollment).where(
                Enrollment.exam_id == exam_id,
                Enrollment.student_id == student_id,
            )
        )
        return result.scalar_one_or_none() is not None


async def _mark_disconnected(exam_id: uuid.UUID, student_id: str) -> None:
    """Stamp ws_disconnected_at on the StudentSession row."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(StudentSession)
            .where(
                StudentSession.exam_id == exam_id,
                StudentSession.student_id == student_id,
            )
            .values(ws_disconnected_at=datetime.now(timezone.utc))
        )
        await db.commit()


async def _heartbeat(ws: WebSocket) -> None:
    """Send a ping frame every 30 seconds to detect stale connections."""
    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
        try:
            await ws.send_text('{"type":"ping"}')
        except Exception:
            return


async def _receive_loop(
    ws: WebSocket,
    exam_id: uuid.UUID,
    student_id: str,
    student_name: str | None,
    student_email: str | None,
) -> None:
    """Forward telemetry frames from the client to storage."""
    async with AsyncSessionLocal() as db:
        while True:
            try:
                raw = await ws.receive_text()
            except WebSocketDisconnect:
                return

            try:
                event_data: dict[str, object] = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event_type = event_data.get("type")
            if event_type in ("ping", "pong"):
                continue

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
                await telemetry_service.store_event(db, exam_id, student_id, event_data)
            except Exception:
                logger.exception("Failed to store telemetry event")


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

    Auth flow:
      1. Decode JWT from ?token= → 4401 on failure.
      2. Check enrollment → 4403 if absent.
      3. Register (exam_id, student_id) → WebSocket in the in-memory dict.
      4. Run a receive loop + 30-second heartbeat concurrently.
      5. On disconnect: unregister and stamp ws_disconnected_at.

    Reconnecting with the same valid JWT is accepted and resumes the session;
    the registry entry is simply replaced with the new socket.
    """
    student_id = _decode_token(token)
    if student_id is None:
        await websocket.accept()
        await websocket.close(code=_WS_UNAUTHORIZED)
        return

    enrolled = await _is_enrolled(exam_id, student_id)
    if not enrolled:
        await websocket.accept()
        await websocket.close(code=_WS_FORBIDDEN)
        return

    await websocket.accept()

    exam_key = str(exam_id)
    async with _registry_lock:
        _connections[exam_key][student_id] = websocket

    logger.info("Telemetry WS opened: exam=%s student=%s", exam_id, student_id)

    async with AsyncSessionLocal() as db:
        student_name, student_email = await _lookup_identity(db, student_id)

    receive_task = asyncio.create_task(
        _receive_loop(
            websocket,
            exam_id,
            student_id,
            student_name,
            student_email,
        )
    )
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))

    try:
        _done, pending = await asyncio.wait(
            {receive_task, heartbeat_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
    finally:
        async with _registry_lock:
            exam_bucket = _connections.get(exam_key, {})
            if exam_bucket.get(student_id) is websocket:
                exam_bucket.pop(student_id, None)
            if not exam_bucket:
                _connections.pop(exam_key, None)

        try:
            await _mark_disconnected(exam_id, student_id)
        except Exception:
            logger.exception(
                "Failed to stamp ws_disconnected_at: exam=%s student=%s",
                exam_id,
                student_id,
            )

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
