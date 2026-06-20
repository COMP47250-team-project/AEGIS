"""Tests for the answer_time component of the signal scorer (AEGIS-47).

The scorer reads question_time events (cumulative per-question durations) and
flags questions answered in under 10s, including 0ms / skipped questions.
"""

import pytest

from app.models.telemetry import TelemetryEvent
from app.services.scorer import compute_component_scores


def _question_time(question_id: str, duration_ms: float) -> TelemetryEvent:
    return TelemetryEvent(
        event_type="question_time",
        payload={"question_id": question_id, "duration_ms": duration_ms},
    )


def test_no_question_time_events_scores_zero() -> None:
    assert compute_component_scores([])["answer_time"] == pytest.approx(0.0)


def test_slow_answers_are_not_flagged() -> None:
    events = [_question_time("q1", 60_000), _question_time("q2", 30_000)]
    assert compute_component_scores(events)["answer_time"] == pytest.approx(0.0)


def test_fast_and_zero_ms_answers_are_flagged() -> None:
    # q1 slow (ok), q2 fast (2s), q3 skipped (0ms) → 2 of 3 flagged
    events = [
        _question_time("q1", 60_000),
        _question_time("q2", 2_000),
        _question_time("q3", 0),
    ]
    assert compute_component_scores(events)["answer_time"] == pytest.approx(2 / 3)


def test_takes_final_cumulative_duration_per_question() -> None:
    # Same question emitted twice (running cumulative): 6s then final 12s.
    # The 12s total should win, so the question is NOT flagged as fast.
    events = [_question_time("q1", 6_000), _question_time("q1", 12_000)]
    assert compute_component_scores(events)["answer_time"] == pytest.approx(0.0)
