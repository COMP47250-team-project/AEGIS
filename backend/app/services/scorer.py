"""Risk score computation service.

Computes a 0–1 integrity risk score from raw telemetry events.
Higher score = more suspicious behaviour.

Formula:
  risk = 0.30 × tab_switch + 0.25 × paste + 0.20 × iki + 0.10 × first_keypress
       + 0.10 × answer_time + 0.05 × resize

The IKI (inter-keystroke-interval) sub-score is the project's formal statistical
component (AEGIS-55): a per-student typing baseline (median + stddev of the first
5 minutes) with each later 2-minute window scored by its z-score against that
baseline. This authoritative score is computed here at exam close; the live
professor view (``app.services.live_monitor``) uses a faster running-mean IKI
estimate for its real-time display.
"""

import logging
import uuid
from datetime import datetime, timezone
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.exam import Enrollment, ExamSession
from app.models.risk import RiskFlag
from app.models.telemetry import SessionScore, StudentBaseline, TelemetryEvent
from app.scoring.baseline_calculator import BaselineResult, compute_baseline
from app.services.audit import STUDENT_FLAGGED, record_audit_event
from app.services.scoring import Event
from app.services.scoring.components.answer_time import answer_time_distribution_score
from app.services.scoring.components.first_keypress import first_keypress_score
from app.services.scoring.components.iki import (
    BASELINE_WINDOW_SECONDS,
    BaselineValues,
    IKIEvent,
    iki_outlier_score,
)
from app.services.scoring.components.paste import paste_score
from app.services.scoring.components.resize import resize_score
from app.services.scoring.components.tab_blur import tab_blur_score

logger = logging.getLogger(__name__)

# Scoring sensitivity presets (AEGIS-84). Each set of weights sums to 1.0.
# Professors pick a preset per exam; lenient de-weights tab/paste for open-book
# multi-tab research exams, strict up-weights them for closed-book exams.
PRESETS: dict[str, dict[str, float]] = {
    "strict": {
        "tab_switch": 0.35,
        "paste": 0.30,
        "iki": 0.20,
        "first_keypress": 0.07,
        "answer_time": 0.05,
        "resize": 0.03,
    },
    "standard": {
        "tab_switch": 0.30,
        "paste": 0.25,
        "iki": 0.20,
        "first_keypress": 0.10,
        "answer_time": 0.10,
        "resize": 0.05,
    },
    "lenient": {
        "tab_switch": 0.15,
        "paste": 0.20,
        "iki": 0.25,
        "first_keypress": 0.15,
        "answer_time": 0.20,
        "resize": 0.05,
    },
}

DEFAULT_PRESET = "standard"

# Back-compat alias — the default weight set.
_WEIGHTS = PRESETS[DEFAULT_PRESET]

# Risk threshold — RiskFlag inserted and WS alert fired on first crossing
RISK_THRESHOLD = 0.70


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _iki_events_for(events: list[TelemetryEvent]) -> list[IKIEvent]:
    """Adapt stored ``key_interval`` rows to the IKI scorer's event shape.

    The browser SDK's ``clientTs`` is dropped at ingestion (see
    ``telemetry_service.store_event``), so we use the server-side
    ``occurred_at`` as the timeline — robust against unsynced client clocks.
    """
    iki_events: list[IKIEvent] = []
    for e in events:
        if e.event_type != "key_interval":
            continue
        interval = e.payload.get("interval_ms")
        if not isinstance(interval, (int, float)):
            continue
        # occurred_at is the server-side timeline; skip rows without one (only
        # possible for un-flushed in-memory objects — never for persisted rows).
        if e.occurred_at is None:
            continue
        iki_events.append(
            IKIEvent(
                event_type="key_interval",
                client_ts_ms=e.occurred_at.timestamp() * 1000.0,
                iki_ms=float(interval),
            )
        )
    return iki_events


def _compute_iki(events: list[TelemetryEvent]) -> tuple[float, BaselineResult]:
    """Compute the z-score IKI sub-score and the baseline it used (AEGIS-55).

    Establishes a per-student typing baseline from the first
    ``BASELINE_WINDOW_SECONDS`` of keystrokes, then scores later 2-minute
    windows by their z-score against that baseline. Returns the 0–1 sub-score
    and the ``BaselineResult`` so the caller can persist it to student_baselines.
    """
    iki_events = _iki_events_for(events)
    if not iki_events:
        return 0.0, BaselineResult()

    exam_start_ms = min(e.client_ts_ms for e in iki_events)
    baseline_end_ms = exam_start_ms + BASELINE_WINDOW_SECONDS * 1000

    # Baseline is built only from intervals inside the opening window.
    baseline_intervals = [
        e.iki_ms
        for e in iki_events
        if e.iki_ms is not None and e.client_ts_ms <= baseline_end_ms
    ]
    baseline = compute_baseline(
        baseline_intervals,
        char_count=len(baseline_intervals),
        first_keypress_latencies_ms=[],
    )
    if not baseline.is_sufficient:
        return 0.0, baseline

    score = iki_outlier_score(
        BaselineValues(
            median_iki_ms=baseline.median_iki_ms or 0.0,
            std_iki_ms=baseline.iki_stddev_ms or 0.0,
            is_sufficient=True,
        ),
        iki_events,
        exam_start_ms,
    )
    return _clamp(score), baseline


async def _upsert_baseline(
    db: AsyncSession,
    exam_id: uuid.UUID,
    student_id: str,
    baseline: BaselineResult,
    now: datetime | None,
) -> None:
    """Insert or update the student_baselines row for one (exam, student)."""
    ts = now or datetime.now(timezone.utc)
    existing = await db.execute(
        select(StudentBaseline).where(
            StudentBaseline.exam_id == exam_id,
            StudentBaseline.student_id == student_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = StudentBaseline(exam_id=exam_id, student_id=student_id)
        db.add(row)
    row.mean_keystroke_interval_ms = baseline.median_iki_ms
    row.keystroke_stddev_ms = baseline.iki_stddev_ms
    row.sample_count = baseline.sample_count
    row.computed_at = ts


def compute_component_scores(
    events: list[TelemetryEvent], iki_score: float | None = None
) -> dict[str, float]:
    """Compute 0–1 sub-score for each of the six signals.

    ``iki_score`` may be passed in when the caller has already run
    ``_compute_iki`` (e.g. the batch scorer, which also needs the baseline) to
    avoid recomputing it; when omitted it is computed here.
    """
    # Adapt ORM rows to the lightweight ScoringEvent shape the component scorers
    # expect (decouples them from SQLAlchemy's Mapped[...] attribute types).
    scoring_events = [Event(e.event_type, e.payload) for e in events]

    if iki_score is None:
        iki_score, _ = _compute_iki(events)

    return {
        "tab_switch": tab_blur_score(scoring_events),
        "paste": paste_score(scoring_events),
        "iki": iki_score,
        "first_keypress": first_keypress_score(scoring_events),
        "answer_time": answer_time_distribution_score(scoring_events),
        "resize": resize_score(scoring_events),
    }


def compute_risk_score(
    component_scores: dict[str, float], preset: str = DEFAULT_PRESET
) -> float:
    """Weighted sum of component scores → aggregate 0–1 risk score.

    ``preset`` selects the weight set (AEGIS-84); an unknown preset falls back
    to the default so a bad value never breaks scoring.
    """
    weights = PRESETS.get(preset, PRESETS[DEFAULT_PRESET])
    return _clamp(sum(weights[k] * component_scores.get(k, 0.0) for k in weights))


async def _ensure_risk_flag(
    db: AsyncSession,
    exam_id: uuid.UUID,
    student_id: str,
    risk_score: float,
    now: datetime,
) -> bool:
    """Insert a RiskFlag if none exists yet for this exam+student.

    Returns True if a new flag was inserted — caller should push a WS alert.
    Returns False if a flag already existed — threshold was already crossed on
    a previous scoring run; do not re-alert (satisfies 'exactly once' rule).
    """
    existing = await db.execute(
        select(RiskFlag).where(
            RiskFlag.exam_id == exam_id,
            RiskFlag.student_id == student_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False

    db.add(
        RiskFlag(
            exam_id=exam_id,
            student_id=student_id,
            threshold_triggered="HIGH",
            risk_score=risk_score,
            flagged_at=now,
        )
    )
    record_audit_event(
        db,
        STUDENT_FLAGGED,
        actor_id=None,  # system-generated by the scorer
        target_id=student_id,
        metadata={"exam_id": str(exam_id), "risk_score": risk_score},
    )
    return True


async def _push_risk_alert(
    exam_id: uuid.UUID,
    student_id: str,
    risk_score: float,
) -> None:
    """Push a risk_alert message to the connected professor WebSocket.

    Late-imports get_professor_websocket to avoid a circular import:
      telemetry.py → scorer.py (already) and scorer.py → telemetry.py (new)
    would form a cycle at module level; a function-scoped import breaks it.

    Failures are caught and logged — a WS push must never block or roll back
    the DB commit that precedes it.
    """
    try:
        from app.routers.telemetry import get_professor_websocket

        ws = await get_professor_websocket(str(exam_id))
        if ws is None:
            logger.debug(
                "No professor connected for exam %s — skipping WS push", exam_id
            )
            return

        alert = {
            "type": "risk_alert",
            "student_id": student_id,
            "risk_score": round(risk_score, 3),
        }
        await ws.send_text(json.dumps(alert))
        logger.info(
            "Risk alert pushed: exam=%s student=%s score=%.3f",
            exam_id,
            student_id,
            risk_score,
        )
    except Exception:
        logger.exception(
            "Failed to push risk alert for exam=%s student=%s", exam_id, student_id
        )


async def compute_and_save_scores(db: AsyncSession, exam_id: uuid.UUID) -> None:
    """Query all telemetry events for a closed exam, compute per-student
    risk scores, and upsert into session_scores."""

    # Load the exam's scoring preset (AEGIS-84) so live and final scores agree.
    preset_row = await db.execute(
        select(ExamSession.scoring_preset).where(ExamSession.id == exam_id)
    )
    preset = preset_row.scalar_one_or_none() or DEFAULT_PRESET

    result = await db.execute(
        select(TelemetryEvent)
        .where(TelemetryEvent.exam_id == exam_id)
        .order_by(TelemetryEvent.occurred_at)
    )
    all_events = list(result.scalars().all())

    # Group events by student
    by_student: dict[str, list[TelemetryEvent]] = {}
    for event in all_events:
        by_student.setdefault(event.student_id, []).append(event)

    # Enrolled students produce zero telemetry when they never join the exam —
    # they still need a SessionScore row (a real 0, not "not yet computed") so
    # the professor report doesn't silently omit them (AEGIS-118).
    enrolled_result = await db.execute(
        select(Enrollment.student_id).where(Enrollment.exam_id == exam_id)
    )
    all_student_ids = set(by_student.keys()) | {row[0] for row in enrolled_result.all()}

    students_to_alert: list[tuple[str, float]] = []
    for student_id in all_student_ids:
        student_events = by_student.get(student_id, [])
        has_telemetry = bool(student_events)

        # Compute the z-score IKI once — reused for the sub-score and persisted
        # as the per-student typing baseline (AEGIS-55).
        iki_score, baseline = _compute_iki(student_events)
        components = compute_component_scores(student_events, iki_score=iki_score)
        aggregate = compute_risk_score(components, preset)

        if baseline.is_sufficient:
            await _upsert_baseline(db, exam_id, student_id, baseline, now=None)

        # Upsert session_scores
        existing_result = await db.execute(
            select(SessionScore).where(
                SessionScore.exam_id == exam_id,
                SessionScore.student_id == student_id,
            )
        )
        score_row = existing_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if score_row is None:
            score_row = SessionScore(
                exam_id=exam_id,
                student_id=student_id,
            )
            db.add(score_row)

        score_row.tab_switch_score = components["tab_switch"]
        score_row.paste_score = components["paste"]
        score_row.keystroke_score = components["iki"]
        score_row.focus_loss_score = components["first_keypress"]
        score_row.answer_timing_score = components["answer_time"]
        score_row.copy_sequence_score = components["resize"]
        score_row.integrity_score = aggregate
        score_row.has_telemetry = has_telemetry
        score_row.computed_at = now

        if aggregate >= RISK_THRESHOLD:
            flag_inserted = await _ensure_risk_flag(
                db, exam_id, student_id, aggregate, now
            )
            if flag_inserted:
                students_to_alert.append((student_id, aggregate))

    await db.commit()

    logger.info(
        "Scores computed for exam %s — %d students processed",
        exam_id,
        len(all_student_ids),
    )
