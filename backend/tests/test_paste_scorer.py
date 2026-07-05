"""Tests for paste_score (AEGIS-54)."""

import pytest

from app.services.scoring import Event
from app.services.scoring.components.paste import paste_score


def _paste(question_id: str, char_count: int = 10) -> Event:
    return Event("paste", {"question_id": question_id, "char_count": char_count})


def test_zero_events_scores_zero() -> None:
    assert paste_score([]) == pytest.approx(0.0)


def test_low_count_single_paste_scores_zero() -> None:
    # A single paste may just be the student copying the question text.
    assert paste_score([_paste("q1")]) == pytest.approx(0.0)


def test_single_large_paste_scores_moderate() -> None:
    # AEGIS-104: a single >200-char paste now scores 0.40. Internal copy/paste
    # is filtered on the client, so a received large paste is external — a real
    # single-shot cheating signal (no extra size bonus on top of the 0.40).
    assert paste_score([_paste("q1", char_count=500)]) == pytest.approx(0.40)


def test_single_paste_at_200_boundary_still_zero() -> None:
    # Exactly 200 is not "> 200": a lone 200-char paste is not "large" -> 0.0.
    assert paste_score([_paste("q1", char_count=200)]) == pytest.approx(0.0)


def test_two_pastes_same_question() -> None:
    assert paste_score([_paste("q1"), _paste("q1")]) == pytest.approx(0.50)


def test_high_count_three_pastes_same_question() -> None:
    assert paste_score([_paste("q1")] * 3) == pytest.approx(0.80)


def test_large_paste_adds_bonus() -> None:
    # Three pastes incl. one >200 chars -> 0.80 + 0.20 -> 1.0.
    events = [_paste("q1"), _paste("q1"), _paste("q1", char_count=250)]
    assert paste_score(events) == pytest.approx(1.0)


def test_aggregate_takes_most_suspicious_question() -> None:
    # q1: 1 paste (0.0); q2: 3 pastes (0.80) -> max 0.80.
    events = [_paste("q1"), _paste("q2"), _paste("q2"), _paste("q2")]
    assert paste_score(events) == pytest.approx(0.80)


def test_char_count_boundary_200_no_bonus() -> None:
    # Exactly 200 is not "> 200", so no bonus: two pastes -> 0.50.
    events = [_paste("q1", char_count=200), _paste("q1", char_count=200)]
    assert paste_score(events) == pytest.approx(0.50)


def test_two_pastes_with_large_paste_bonus() -> None:
    # Two pastes (0.50) with one > 200 chars -> +0.20 -> 0.70.
    events = [_paste("q1"), _paste("q1", char_count=201)]
    assert paste_score(events) == pytest.approx(0.70)


def test_missing_char_count_treated_as_zero() -> None:
    # No char_count field -> 0 chars -> no bonus: two pastes -> 0.50.
    events = [Event("paste", {"question_id": "q1"}), Event("paste", {"question_id": "q1"})]
    assert paste_score(events) == pytest.approx(0.50)


def test_ignores_unrelated_event_types() -> None:
    events = [Event("tab_blur", {}), Event("key_interval", {"interval_ms": 5})]
    assert paste_score(events) == pytest.approx(0.0)


def test_pastes_to_different_questions_do_not_accumulate() -> None:
    # One paste each to three different questions -> each 0.0 -> max 0.0.
    events = [_paste("q1"), _paste("q2"), _paste("q3")]
    assert paste_score(events) == pytest.approx(0.0)
