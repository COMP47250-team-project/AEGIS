"""iki_outlier_score — AEGIS-55.

Compares a student's mid-exam inter-keystroke intervals (IKI) against their
personal baseline established in the first 5 minutes of the exam.

Algorithm:
  1. Split events after T+5min into 2-minute windows.
  2. For each window with ≥10 keystrokes, compute the window median IKI.
  3. Calculate Z-score: z = (window_median - baseline_median) / baseline_std
  4. Score the window: sigmoid(abs(z) - 2)
  5. Final score = max score across all windows.

Special cases:
  - Insufficient baseline → 0.0 (no data to compare against)
  - Window with <10 keystrokes → skip
  - Very slow typing (z <= -3) → cap score at 0.3

Signal weight in the aggregate scorer: 0.20
"""

import math
import statistics
from typing import NamedTuple

# Baseline window length in seconds (first 5 minutes).
BASELINE_WINDOW_SECONDS = 5 * 60

# Each scoring window is 2 minutes.
SCORING_WINDOW_SECONDS = 2 * 60

# Minimum keystrokes per window to compute a reliable median.
MIN_KEYSTROKES_PER_WINDOW = 10

# Score cap for very slow typing (z <= -3 in the slow direction).
SLOW_TYPING_SCORE_CAP = 0.3


def _sigmoid(x: float) -> float:
    """Logistic sigmoid function: 1 / (1 + e^-x)."""
    return 1.0 / (1.0 + math.exp(-x))


def _score_window(z: float) -> float:
    """Map a Z-score to a 0–1 suspicion score.

    Very fast typing (high positive z) → high score.
    Very slow typing (z <= -3) → capped at SLOW_TYPING_SCORE_CAP.
    """
    if z <= -3.0:
        return SLOW_TYPING_SCORE_CAP
    return _sigmoid(abs(z) - 2.0)


class IKIEvent(NamedTuple):
    """Minimal shape for a telemetry event used by the IKI scorer."""

    event_type: str
    client_ts_ms: float  # Unix timestamp in milliseconds
    iki_ms: float | None = None  # inter-keystroke interval in ms


class BaselineValues(NamedTuple):
    """Extracted baseline values needed by the scorer."""

    median_iki_ms: float
    std_iki_ms: float
    is_sufficient: bool


def iki_outlier_score(
    baseline: BaselineValues,
    events: list[IKIEvent],
    exam_start_ms: float,
) -> float:
    """Return a 0–1 IKI outlier risk sub-score for one session.

    Args:
        baseline: the student's typing baseline from the first 5 minutes.
        events: list of IKI telemetry events for the whole session.
        exam_start_ms: Unix timestamp (ms) when the exam started — used to
            determine the baseline window boundary.

    Returns:
        0.0 if the baseline is insufficient or no scorable windows exist.
        Otherwise the maximum per-window score across all 2-minute windows
        after T+5min.
    """
    if not baseline.is_sufficient:
        return 0.0

    if baseline.std_iki_ms < 1e-9:
        return 0.0

    baseline_end_ms = exam_start_ms + BASELINE_WINDOW_SECONDS * 1000

    # Collect IKI samples from events that occurred AFTER the baseline window.
    post_baseline_events = [
        e
        for e in events
        if e.event_type == "key_interval"
        and e.client_ts_ms > baseline_end_ms
        and e.iki_ms is not None
    ]

    if not post_baseline_events:
        return 0.0

    # Split into 2-minute windows and score each.
    window_scores: list[float] = []
    window_start_ms = baseline_end_ms

    while True:
        window_end_ms = window_start_ms + SCORING_WINDOW_SECONDS * 1000
        window_events = [
            e
            for e in post_baseline_events
            if window_start_ms <= e.client_ts_ms < window_end_ms
            and e.iki_ms is not None
        ]

        if not window_events:
            break

        if len(window_events) >= MIN_KEYSTROKES_PER_WINDOW:
            ikis = [e.iki_ms for e in window_events if e.iki_ms is not None]
            window_median = statistics.median(ikis)
            z = (window_median - baseline.median_iki_ms) / baseline.std_iki_ms
            window_scores.append(_score_window(z))

        window_start_ms = window_end_ms

    return max(window_scores) if window_scores else 0.0
