"""Tests for tab_blur_score (AEGIS-54)."""

import pytest

from app.services.scoring import Event
from app.services.scoring.components.tab_blur import tab_blur_score


def _blur() -> Event:
    return Event("tab_blur", {})


def _return(duration_ms: float) -> Event:
    return Event("tab_return", {"duration_away_ms": duration_ms})


def test_zero_events_scores_zero() -> None:
    assert tab_blur_score([]) == pytest.approx(0.0)


def test_low_count_single_long_blur() -> None:
    # One blur, away 5s (>=2s) -> effective count 1.0 -> 0.15.
    assert tab_blur_score([_blur(), _return(5_000)]) == pytest.approx(0.15)


def test_high_count_four_long_blurs() -> None:
    events: list[Event] = []
    for _ in range(4):
        events += [_blur(), _return(5_000)]
    assert tab_blur_score(events) == pytest.approx(0.85)


def test_short_blurs_weighted_half() -> None:
    # Two blurs, both <2s away -> effective 1.0 -> 0.15 (vs 0.35 at full weight).
    events = [_blur(), _return(500), _blur(), _return(900)]
    assert tab_blur_score(events) == pytest.approx(0.15)


def test_blur_without_return_counts_full() -> None:
    # No return recorded (still away at session end) -> full weight 1.0 -> 0.15.
    assert tab_blur_score([_blur()]) == pytest.approx(0.15)


def test_2000ms_boundary_is_not_short() -> None:
    # Exactly 2s is not "short" (< 2000), so both count full -> 2.0 -> 0.35.
    events = [_blur(), _return(2_000), _blur(), _return(2_000)]
    assert tab_blur_score(events) == pytest.approx(0.35)


def test_score_caps_at_one() -> None:
    events: list[Event] = []
    for _ in range(20):
        events += [_blur(), _return(5_000)]
    assert tab_blur_score(events) == pytest.approx(1.0)


def test_returns_without_any_blur_score_zero() -> None:
    # tab_return frames but no tab_blur -> nothing to count.
    assert tab_blur_score([_return(5_000), _return(100)]) == pytest.approx(0.0)


def test_ignores_unrelated_event_types() -> None:
    events = [Event("paste", {"char_count": 9}), Event("key_interval", {"interval_ms": 5})]
    assert tab_blur_score(events) == pytest.approx(0.0)


def test_return_with_missing_duration_counts_full() -> None:
    # Return frame carries no duration -> the blur can't be proven short -> full.
    events = [_blur(), Event("tab_return", {})]
    assert tab_blur_score(events) == pytest.approx(0.15)


def test_fractional_count_interpolates() -> None:
    # One short (0.5) + two long (2.0) = 2.5 -> between 0.35 and 0.60 -> 0.475.
    events = [_blur(), _return(500), _blur(), _return(5_000), _blur(), _return(5_000)]
    assert tab_blur_score(events) == pytest.approx(0.475)
