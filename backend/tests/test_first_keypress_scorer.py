"""Tests for first_keypress_score (AEGIS-56)."""

from app.services.scoring import Event
from app.services.scoring.components.first_keypress import first_keypress_score


def _answer_start(elapsed_ms: float) -> Event:
    return Event("answer_start", {"elapsed_ms": elapsed_ms})


def test_fast_first_keypress_is_flagged() -> None:
    # First keypress 5s after start (< 10s) -> 0.2.
    assert first_keypress_score([_answer_start(5_000)]) == 0.2


def test_slow_first_keypress_not_flagged() -> None:
    # 15s -> 0.0; 10s exactly is also not flagged (strict <).
    assert first_keypress_score([_answer_start(15_000)]) == 0.0
    assert first_keypress_score([_answer_start(10_000)]) == 0.0


def test_no_answer_start_scores_zero() -> None:
    assert first_keypress_score([Event("paste", {"char_count": 5})]) == 0.0


def test_uses_first_answer_start_only() -> None:
    # First is slow -> 0.0, even though a later question was typed quickly.
    assert first_keypress_score([_answer_start(12_000), _answer_start(1_000)]) == 0.0
