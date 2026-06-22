"""Tests for telemetry event persistence.

Regression: store_event used to persist the whole browser frame (minus
type/sessionId), nesting the real signal fields under payload.payload — which
the scorer reads flat, so every payload-based score (iki, first_keypress,
answer_time) silently scored 0. Events must be stored with the inner payload
flat.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import TelemetryEvent
from app.services.scorer import compute_component_scores
from app.services.telemetry_service import store_event


@pytest.mark.asyncio
async def test_store_event_persists_inner_payload_flat(db_session: AsyncSession) -> None:
    exam_id = uuid.uuid4()
    frame = {
        "type": "key_interval",
        "sessionId": "sess-1",
        "clientTs": 1700000000000,
        "payload": {"interval_ms": 42, "question_id": "q1"},
    }

    await store_event(db_session, exam_id, "student-1", frame)

    result = await db_session.execute(
        select(TelemetryEvent).where(TelemetryEvent.exam_id == exam_id)
    )
    event = result.scalar_one()

    assert event.event_type == "key_interval"
    # Signal fields stored flat — not nested under a "payload" key.
    assert event.payload == {"interval_ms": 42, "question_id": "q1"}


@pytest.mark.asyncio
async def test_stored_event_is_readable_by_scorer(db_session: AsyncSession) -> None:
    exam_id = uuid.uuid4()
    # Two fast keystroke intervals → scorer should flag a high iki score.
    for _ in range(2):
        await store_event(
            db_session,
            exam_id,
            "student-1",
            {"type": "key_interval", "sessionId": "s",
             "payload": {"interval_ms": 20}},
        )

    result = await db_session.execute(
        select(TelemetryEvent).where(TelemetryEvent.exam_id == exam_id)
    )
    events = list(result.scalars().all())

    # (400 - 20) / 400 = 0.95 — only reachable if the payload is read flat.
    assert compute_component_scores(events)["iki"] == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_store_event_missing_payload_defaults_empty(
    db_session: AsyncSession,
) -> None:
    exam_id = uuid.uuid4()
    await store_event(db_session, exam_id, "student-1", {"type": "resize"})

    result = await db_session.execute(
        select(TelemetryEvent).where(TelemetryEvent.exam_id == exam_id)
    )
    event = result.scalar_one()
    assert event.payload == {}
