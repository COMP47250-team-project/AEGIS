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
    event = TelemetryEvent(
        exam_id=exam_id,
        student_id=student_id,
        event_type=str(event_data.get("type", "unknown"))[:64],
        payload={k: v for k, v in event_data.items() if k not in ("type", "sessionId")},
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()
