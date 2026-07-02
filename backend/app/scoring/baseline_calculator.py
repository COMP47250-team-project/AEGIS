"""Pure baseline calculator for student typing patterns.

Computes a student's typing baseline from the first 5 minutes of an exam
session — before cheating is statistically likely. This baseline is later
used by the IKI outlier scorer to compare mid-exam typing rhythm against
the student's own established pattern.

This module performs no I/O — no database queries, no network calls — so
it can be unit tested in complete isolation. Persisting the result to the
student_baselines table is the caller's responsibility.
"""

import statistics

from pydantic import BaseModel, Field

# Minimum keystrokes required before a baseline is considered statistically
# meaningful — fewer than this and the median/stddev are too noisy to trust.
MIN_KEYSTROKES_FOR_BASELINE = 50

# Baseline window length in seconds (first 5 minutes of the exam).
BASELINE_WINDOW_SECONDS = 5 * 60


class BaselineResult(BaseModel):
    """Computed typing baseline for one student's exam session.

    ``is_sufficient`` is False whenever the student produced fewer than
    MIN_KEYSTROKES_FOR_BASELINE keystrokes inside the baseline window — in
    that case all numeric fields are None and downstream scorers should
    treat the IKI outlier score as 0.0 (no baseline to compare against).
    """

    median_iki_ms: float | None = Field(default=None)
    iki_stddev_ms: float | None = Field(default=None)
    typing_speed_chars_per_min: float | None = Field(default=None)
    avg_time_to_first_keypress_ms: float | None = Field(default=None)
    sample_count: int = Field(default=0)
    is_sufficient: bool = Field(default=False)


def compute_baseline(
    iki_samples_ms: list[float],
    char_count: int,
    first_keypress_latencies_ms: list[float],
) -> BaselineResult:
    """Pure function: compute a student's typing baseline from raw samples
    collected during the first 5 minutes of an exam session.

    Args:
        iki_samples_ms: inter-keystroke intervals (ms) observed in the
            baseline window.
        char_count: total characters typed in the baseline window — used
            to compute typing speed and to decide sufficiency.
        first_keypress_latencies_ms: time-to-first-keypress (ms) for each
            question the student opened during the baseline window.

    Returns:
        A BaselineResult. If fewer than MIN_KEYSTROKES_FOR_BASELINE
        keystrokes were observed, ``is_sufficient`` is False and all
        numeric fields are None — the caller's IKI outlier scorer should
        then default to a score of 0.0 rather than flagging a student who
        simply didn't type enough in the baseline window to measure.
    """
    sample_count = len(iki_samples_ms)

    if (
        sample_count < MIN_KEYSTROKES_FOR_BASELINE
        or char_count < MIN_KEYSTROKES_FOR_BASELINE
    ):
        return BaselineResult(
            sample_count=sample_count,
            is_sufficient=False,
        )

    median_iki = statistics.median(iki_samples_ms)
    # stdev requires at least 2 data points; guard defensively even though
    # the MIN_KEYSTROKES_FOR_BASELINE check above already guarantees this.
    stddev_iki = statistics.stdev(iki_samples_ms) if sample_count > 1 else 0.0

    typing_speed = char_count / (BASELINE_WINDOW_SECONDS / 60.0)

    avg_first_keypress = (
        statistics.mean(first_keypress_latencies_ms)
        if first_keypress_latencies_ms
        else None
    )

    return BaselineResult(
        median_iki_ms=median_iki,
        iki_stddev_ms=stddev_iki,
        typing_speed_chars_per_min=typing_speed,
        avg_time_to_first_keypress_ms=avg_first_keypress,
        sample_count=sample_count,
        is_sufficient=True,
    )
