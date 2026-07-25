"""Score persistence tests (AEGIS-68): upsert idempotency + risk_flag trigger.

compute_and_save_scores() reads a student's telemetry, writes one SessionScore
row (upserted), and — when the aggregate crosses RISK_THRESHOLD — inserts one
RiskFlag exactly once. These paths had no direct coverage.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk import RiskFlag
from app.models.telemetry import SessionScore, StudentBaseline, TelemetryEvent
from app.services.scorer import RISK_THRESHOLD, compute_and_save_scores

# Fixed timeline base so baseline/anomaly windows are deterministic.
_T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


async def _add_high_risk_events(
    db: AsyncSession, exam_id: uuid.UUID, student_id: str
) -> None:
    """Insert a session that saturates tab_switch + paste and shows a genuine
    keystroke-cadence anomaly (AEGIS-55 z-score path), pushing the weighted
    aggregate over RISK_THRESHOLD.
    """
    events: list[TelemetryEvent] = []
    # Many tab blurs (no return → each full weight) → tab_switch saturates (1.0).
    for _ in range(10):
        events.append(
            TelemetryEvent(
                exam_id=exam_id,
                student_id=student_id,
                event_type="tab_blur",
                payload={},
                occurred_at=_T0,
            )
        )
    # Repeated large pastes to one question → paste score high (1.0).
    for _ in range(3):
        events.append(
            TelemetryEvent(
                exam_id=exam_id,
                student_id=student_id,
                event_type="paste",
                payload={"question_id": "q1", "char_count": 400},
                occurred_at=_T0,
            )
        )
    # Keystroke baseline: 60 intervals alternating 150/250 ms in the first 5 min
    # → median 200 ms, stddev ~50 ms (>= 50 samples makes the baseline sufficient).
    for i in range(60):
        events.append(
            TelemetryEvent(
                exam_id=exam_id,
                student_id=student_id,
                event_type="key_interval",
                payload={"interval_ms": 150 if i % 2 == 0 else 250},
                occurred_at=_T0 + timedelta(seconds=i * 4),  # 0..236s, all in-window
            )
        )
    # Anomalous later window (T+6min): 15 intervals at 450 ms → z ≈ +5 vs baseline
    # → IKI sub-score ~0.95. Combined with tab+paste this clears 0.70.
    for i in range(15):
        events.append(
            TelemetryEvent(
                exam_id=exam_id,
                student_id=student_id,
                event_type="key_interval",
                payload={"interval_ms": 450},
                occurred_at=_T0 + timedelta(seconds=360 + i),
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

    # AEGIS-55: the z-score IKI path persists the per-student typing baseline.
    baseline = (
        await db_session.execute(
            select(StudentBaseline).where(
                StudentBaseline.exam_id == exam_id,
                StudentBaseline.student_id == student_id,
            )
        )
    ).scalar_one()
    assert baseline.sample_count >= 50
    assert baseline.keystroke_stddev_ms and baseline.keystroke_stddev_ms > 0

    flags = (
        (
            await db_session.execute(
                select(RiskFlag).where(
                    RiskFlag.exam_id == exam_id, RiskFlag.student_id == student_id
                )
            )
        )
        .scalars()
        .all()
    )
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
        (
            await db_session.execute(
                select(SessionScore).where(
                    SessionScore.exam_id == exam_id,
                    SessionScore.student_id == student_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(scores) == 1

    flags = (
        (
            await db_session.execute(
                select(RiskFlag).where(
                    RiskFlag.exam_id == exam_id, RiskFlag.student_id == student_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(flags) == 1
