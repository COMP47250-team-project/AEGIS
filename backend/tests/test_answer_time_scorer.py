"""Tests for answer_time_distribution_score (AEGIS-56)."""

import pytest

from app.services.scoring import Event
from app.services.scoring.components.answer_time import answer_time_distribution_score


def _qt(qid: str, duration_ms: float, total_questions: int | None = None) -> Event:
    payload: dict = {"question_id": qid, "duration_ms": duration_ms}
    if total_questions is not None:
        payload["total_questions"] = total_questions
    return Event("question_time", payload)


def test_no_events_scores_zero() -> None:
    assert answer_time_distribution_score([]) == pytest.approx(0.0)


def test_even_times_have_zero_cv() -> None:
    events = [_qt("q1", 60_000), _qt("q2", 60_000), _qt("q3", 60_000)]
    assert answer_time_distribution_score(events) == pytest.approx(0.0)


def test_uneven_times_scored_by_cv() -> None:
    # durations 10/60/110s -> CV ~0.680 -> *0.8 ~0.544 (3 questions, no bonus).
    events = [_qt("q1", 10_000), _qt("q2", 60_000), _qt("q3", 110_000)]
    assert answer_time_distribution_score(events) == pytest.approx(0.5443, abs=1e-3)


def test_short_answer_bonus_on_long_exam() -> None:
    # 6 equal 20s answers -> CV 0; exam >5 questions with <30s answers -> +0.20.
    events = [_qt(f"q{i}", 20_000, total_questions=6) for i in range(6)]
    assert answer_time_distribution_score(events) == pytest.approx(0.2)


def test_no_bonus_when_five_or_fewer_questions() -> None:
    events = [_qt(f"q{i}", 20_000, total_questions=5) for i in range(5)]
    assert answer_time_distribution_score(events) == pytest.approx(0.0)


def test_takes_largest_cumulative_duration_per_question() -> None:
    # Same question emitted twice (running cumulative) collapses to one value.
    events = [_qt("q1", 6_000), _qt("q1", 12_000)]
    assert answer_time_distribution_score(events) == pytest.approx(0.0)
