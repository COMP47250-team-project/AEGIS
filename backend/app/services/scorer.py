"""Risk score computation service.

Computes a 0–1 integrity risk score from raw telemetry events.
Higher score = more suspicious behaviour.

Formula:
  risk = 0.30 × tab_switch + 0.25 × paste + 0.20 × iki + 0.10 × first_keypress
       + 0.10 × answer_time + 0.05 × resize
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import SessionScore, TelemetryEvent
from app.services.scoring import Event
from app.services.scoring.components.paste import paste_score
from app.services.scoring.components.tab_blur import tab_blur_score

logger = logging.getLogger(__name__)

_WEIGHTS = {
    "tab_switch": 0.30,
    "paste": 0.25,
    "iki": 0.20,
    "first_keypress": 0.10,
    "answer_time": 0.10,
    "resize": 0.05,
}


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def compute_component_scores(events: list[TelemetryEvent]) -> dict[str, float]:
    """Compute 0–1 sub-score for each of the six signals."""
    # Adapt ORM rows to the lightweight ScoringEvent shape the component scorers
    # expect (decouples them from SQLAlchemy's Mapped[...] attribute types).
    scoring_events = [Event(e.event_type, e.payload) for e in events]
    resize_count = sum(1 for e in events if e.event_type == "resize")

    # IKI: very short intervals (< 50ms) indicate pasted/AI-generated text
    iki_events = [e for e in events if e.event_type == "key_interval"]
    if iki_events:
        intervals = []
        for e in iki_events:
            v = e.payload.get("interval_ms")
            if isinstance(v, (int, float)):
                intervals.append(float(v))
        if intervals:
            mean_iki = sum(intervals) / len(intervals)
            # Very fast typing (<50ms avg) → score ~1.0, normal (>400ms) → ~0
            iki_score = _clamp((400.0 - mean_iki) / 400.0)
        else:
            iki_score = 0.0
    else:
        iki_score = 0.0

    # first_keypress: very quick responses (< 1s) on most questions → suspicious
    first_keypress_events = [e for e in events if e.event_type == "answer_start"]
    if first_keypress_events:
        quick = sum(
            1
            for e in first_keypress_events
            if isinstance(e.payload.get("elapsed_ms"), (int, float))
            and float(e.payload["elapsed_ms"]) < 1000  # type: ignore[arg-type]
        )
        first_keypress_score = _clamp(quick / max(len(first_keypress_events), 1))
    else:
        first_keypress_score = 0.0

    # answer_time: very short cumulative time on a question → suspicious
    # (pre-typed answers, copy-paste, or skipped). question_time events carry
    # a running cumulative duration, and one event is emitted per question at
    # submit, so we take the final (max) duration per question_id before scoring.
    question_time_events = [e for e in events if e.event_type == "question_time"]
    if question_time_events:
        durations: dict[str, float] = {}
        for e in question_time_events:
            qid = e.payload.get("question_id")
            v = e.payload.get("duration_ms")
            if isinstance(qid, str) and isinstance(v, (int, float)):
                durations[qid] = max(durations.get(qid, 0.0), float(v))
        if durations:
            # Questions answered in under 10s (including 0ms / skipped) are fast.
            fast = sum(1 for d in durations.values() if d < 10_000)
            answer_time_score = _clamp(fast / len(durations))
        else:
            answer_time_score = 0.0
    else:
        answer_time_score = 0.0

    return {
        "tab_switch": tab_blur_score(scoring_events),
        "paste": paste_score(scoring_events),
        "iki": iki_score,
        "first_keypress": first_keypress_score,
        "answer_time": answer_time_score,
        "resize": _clamp(resize_count / 5.0),
    }


def compute_risk_score(component_scores: dict[str, float]) -> float:
    """Weighted sum of component scores → aggregate 0–1 risk score."""
    return _clamp(sum(_WEIGHTS[k] * component_scores.get(k, 0.0) for k in _WEIGHTS))


async def compute_and_save_scores(db: AsyncSession, exam_id: uuid.UUID) -> None:
    """Query all telemetry events for a closed exam, compute per-student
    risk scores, and upsert into session_scores."""

    result = await db.execute(
        select(TelemetryEvent).where(TelemetryEvent.exam_id == exam_id)
    )
    all_events = list(result.scalars().all())

    # Group events by student
    by_student: dict[str, list[TelemetryEvent]] = {}
    for event in all_events:
        by_student.setdefault(event.student_id, []).append(event)

    for student_id, student_events in by_student.items():
        components = compute_component_scores(student_events)
        aggregate = compute_risk_score(components)

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
        score_row.computed_at = now

    await db.commit()
    logger.info(
        "Scores computed for exam %s — %d students processed",
        exam_id,
        len(by_student),
    )
