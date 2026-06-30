"""Telemetry event persistence service.

This module focuses on storing events in the database. Validation and
messaging are handled by the WebSocket acceptor so that WS error replies
can be sent immediately.
"""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import TelemetryEvent

logger = logging.getLogger(__name__)


async def store_event(
    db: AsyncSession,
    exam_id: uuid.UUID,
    student_id: str,
    event_data: dict[str, object],
) -> None:
    """Persist one raw browser telemetry event to the database.

    Invalid or missing fields are silently defaulted — telemetry must never
    block or raise errors visible to the student. Any DB errors are logged
    but not re-raised to avoid breaking the WebSocket connection.
    """
    raw_payload = event_data.get("payload")
    payload = raw_payload if isinstance(raw_payload, dict) else {}

    event = TelemetryEvent(
        exam_id=exam_id,
        student_id=student_id,
        event_type=str(event_data.get("type", "unknown"))[:64],
        payload=payload,
        occurred_at=datetime.now(timezone.utc),
    )
    try:
        db.add(event)
        await db.commit()
    except Exception:  # pragma: no cover - DB issues are environmental
        logger.exception(
            "Failed to write telemetry event to DB for exam=%s student=%s",
            exam_id,
            student_id,
        )

