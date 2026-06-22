"""Telemetry event persistence service."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import TelemetryEvent


async def store_event(
    db: AsyncSession,
    exam_id: uuid.UUID,
    student_id: str,
    event_data: dict[str, object],
) -> None:
    """Persist one raw browser telemetry event to the database.

    Invalid or missing fields are silently defaulted — telemetry must never
    block or raise errors visible to the student.
    """
    # The browser sends { type, sessionId, clientTs, payload }. Persist the
    # inner `payload` directly so signal fields (interval_ms, duration_ms, …)
    # sit at the top level — the shape the scorer reads. Previously the whole
    # frame (minus type/sessionId) was stored, nesting fields under
    # payload.payload and zeroing every payload-based score.
    raw_payload = event_data.get("payload")
    payload = raw_payload if isinstance(raw_payload, dict) else {}

    event = TelemetryEvent(
        exam_id=exam_id,
        student_id=student_id,
        event_type=str(event_data.get("type", "unknown"))[:64],
        payload=payload,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()
