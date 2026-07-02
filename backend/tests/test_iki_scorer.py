"""Unit tests for the IKI outlier scorer — AEGIS-55.

The ticket requires exactly 4 test cases:
  1. No baseline (insufficient)
  2. Normal baseline Z=0
  3. Suspicious Z=3.5
  4. Slow typing Z=-3
"""

import pytest

from app.services.scoring.components.iki import (
    SLOW_TYPING_SCORE_CAP,
    BaselineValues,
    IKIEvent,
    iki_outlier_score,
)

# Exam start time in ms (arbitrary fixed value for tests)
EXAM_START_MS = 1_000_000.0

# Baseline window ends at T+5min = 300_000ms after start
BASELINE_END_MS = EXAM_START_MS + 300_000.0

# Place test events 60s into the first scoring window (well after baseline)
WINDOW_MS = BASELINE_END_MS + 60_000.0


def _make_baseline(
    median: float = 200.0,
    std: float = 50.0,
    sufficient: bool = True,
) -> BaselineValues:
    return BaselineValues(
        median_iki_ms=median,
        std_iki_ms=std,
        is_sufficient=sufficient,
    )


def _make_events(
    median_iki: float,
    count: int = 15,
    ts: float = WINDOW_MS,
) -> list[IKIEvent]:
    """Generate ``count`` IKI events all with the same interval."""
    return [
        IKIEvent(
            event_type="key_interval", client_ts_ms=ts + i * 100, iki_ms=median_iki
        )
        for i in range(count)
    ]


class TestNoBaseline:
    def test_insufficient_baseline_returns_zero(self) -> None:
        """Ticket: insufficient baseline → score = 0.0."""
        baseline = _make_baseline(sufficient=False)
        events = _make_events(median_iki=200.0)

        result = iki_outlier_score(baseline, events, EXAM_START_MS)

        assert result == pytest.approx(0.0)

    def test_zero_std_baseline_returns_zero(self) -> None:
        """Edge case: baseline std of 0 would cause division by zero — return 0."""
        baseline = _make_baseline(std=0.0, sufficient=True)
        events = _make_events(median_iki=200.0)

        result = iki_outlier_score(baseline, events, EXAM_START_MS)

        assert result == pytest.approx(0.0)

    def test_no_events_after_baseline_returns_zero(self) -> None:
        baseline = _make_baseline()
        # Events are all within the baseline window (before T+5min)
        events = [
            IKIEvent(
                event_type="key_interval",
                client_ts_ms=EXAM_START_MS + 1000,
                iki_ms=200.0,
            )
        ]

        result = iki_outlier_score(baseline, events, EXAM_START_MS)

        assert result == pytest.approx(0.0)


class TestNormalTypingZeroZ:
    def test_z_score_zero_gives_low_score(self) -> None:
        """Ticket: normal baseline Z=0 → low suspicion score."""
        baseline = _make_baseline(median=200.0, std=50.0)
        # Window median matches baseline exactly → Z = 0
        events = _make_events(median_iki=200.0)

        result = iki_outlier_score(baseline, events, EXAM_START_MS)

        # sigmoid(abs(0) - 2) = sigmoid(-2) ≈ 0.119 — low suspicion
        assert result == pytest.approx(0.119, abs=0.01)
        assert result < 0.2


class TestSuspiciousTypingHighZ:
    def test_z_score_3_5_gives_high_score(self) -> None:
        """Ticket: suspicious Z=3.5 → high suspicion score."""
        baseline = _make_baseline(median=200.0, std=50.0)
        # Window median = 375ms → Z = (375 - 200) / 50 = 3.5
        events = _make_events(median_iki=375.0)

        result = iki_outlier_score(baseline, events, EXAM_START_MS)

        # sigmoid(abs(3.5) - 2) = sigmoid(1.5) ≈ 0.818 — high suspicion
        assert result == pytest.approx(0.818, abs=0.01)
        assert result > 0.7


class TestSlowTypingNegativeZ:
    def test_slow_typing_z_minus_3_capped_at_0_3(self) -> None:
        """Ticket: very slow typing Z=-3 → score capped at 0.3."""
        baseline = _make_baseline(median=200.0, std=50.0)
        # Window median = 50ms → Z = (50 - 200) / 50 = -3.0
        events = _make_events(median_iki=50.0)

        result = iki_outlier_score(baseline, events, EXAM_START_MS)

        assert result == pytest.approx(SLOW_TYPING_SCORE_CAP)

    def test_window_below_min_keystrokes_is_skipped(self) -> None:
        """Windows with fewer than 10 keystrokes must be skipped."""
        baseline = _make_baseline(median=200.0, std=50.0)
        # Only 5 events — below MIN_KEYSTROKES_PER_WINDOW
        events = _make_events(median_iki=375.0, count=5)

        result = iki_outlier_score(baseline, events, EXAM_START_MS)

        assert result == pytest.approx(0.0)
