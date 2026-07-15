"""Score persistence tests (AEGIS-68): upsert idempotency + risk_flag trigger.

compute_and_save_scores() reads a student's telemetry, writes one SessionScore
row (upserted), and — when the aggregate crosses RISK_THRESHOLD — inserts one
RiskFlag exactly once. These paths had no direct coverage.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk import RiskFlag
from app.models.telemetry import SessionScore, TelemetryEvent
from app.services.scorer import RISK_THRESHOLD, compute_and_save_scores


async def _add_high_risk_events(
    db: AsyncSession, exam_id: uuid.UUID, student_id: str
) -> None:
    """Insert enough suspicious events to push the aggregate over threshold."""
    events: list[TelemetryEvent] = []
    # Many tab blurs (no return → each full weight) → tab_switch saturates.
    for _ in range(10):
        events.append(
            TelemetryEvent(exam_id=exam_id, student_id=student_id, event_type="tab_blur", payload={})
        )
    # Repeated large pastes to one question → paste score high.
    for _ in range(3):
        events.append(
            TelemetryEvent(
                exam_id=exam_id,
                student_id=student_id,
                event_type="paste",
                payload={"question_id": "q1", "char_count": 400},
            )
        )
    # Very fast typing → iki high.
    for _ in range(5):
        events.append(
            TelemetryEvent(
                exam_id=exam_id,
                student_id=student_id,
                event_type="key_interval",
                payload={"interval_ms": 20},
            )
        )
    db.add_all(events)
    await db.commit()


@pytest.mark.asyncio
async def test_risk_flag_triggered_above_threshold(db_session: AsyncSession) -> None:
    exam_id = uuid.uuid4()
    student_id = "student-flag-1"
    await _add_high_risk_events(db_session, exam_id, student_id)

    await compute_and_save_scores(db_session, exam_id)

    score = (
        await db_session.execute(
            select(SessionScore).where(
                SessionScore.exam_id == exam_id,
                SessionScore.student_id == student_id,
            )
        )
    ).scalar_one()
    assert score.integrity_score >= RISK_THRESHOLD

    flags = (
        await db_session.execute(
            select(RiskFlag).where(
                RiskFlag.exam_id == exam_id, RiskFlag.student_id == student_id
            )
        )
    ).scalars().all()
    assert len(flags) == 1
    assert flags[0].threshold_triggered == "HIGH"


@pytest.mark.asyncio
async def test_recompute_is_idempotent(db_session: AsyncSession) -> None:
    exam_id = uuid.uuid4()
    student_id = "student-flag-2"
    await _add_high_risk_events(db_session, exam_id, student_id)

    # Score twice — the second run must not duplicate the score or the flag.
    await compute_and_save_scores(db_session, exam_id)
    await compute_and_save_scores(db_session, exam_id)

    scores = (
        await db_session.execute(
            select(SessionScore).where(
                SessionScore.exam_id == exam_id, SessionScore.student_id == student_id
            )
        )
    ).scalars().all()
    assert len(scores) == 1

    flags = (
        await db_session.execute(
            select(RiskFlag).where(
                RiskFlag.exam_id == exam_id, RiskFlag.student_id == student_id
            )
        )
    ).scalars().all()
    assert len(flags) == 1
