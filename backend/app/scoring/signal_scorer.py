"""Pure signal scoring engine.

Computes a weighted composite risk score (0.0–1.0) from the six behavioural
signal components. This module performs no I/O — no database queries, no
network calls — so it can be unit tested in complete isolation.

Formula:
    risk_score = (
        0.30 * tab_blur_score +
        0.25 * paste_score +
        0.20 * iki_outlier_score +
        0.10 * first_keypress_score +
        0.10 * answer_time_score +
        0.05 * resize_score
    )
"""

from pydantic import BaseModel, Field

# Weights must sum to 1.0
WEIGHTS: dict[str, float] = {
    "tab_blur_score": 0.30,
    "paste_score": 0.25,
    "iki_outlier_score": 0.20,
    "first_keypress_score": 0.10,
    "answer_time_score": 0.10,
    "resize_score": 0.05,
}


def _clamp(value: float) -> float:
    """Clamp a value to the inclusive [0.0, 1.0] range."""
    return max(0.0, min(1.0, value))


class SignalScoreResult(BaseModel):
    """The six normalised component scores plus the weighted aggregate.

    Each component is in [0.0, 1.0] where 0 = no suspicion, 1 = strong
    suspicion. ``risk_score`` is the weighted composite of all six.
    """

    tab_blur_score: float = Field(default=0.0, ge=0.0, le=1.0)
    paste_score: float = Field(default=0.0, ge=0.0, le=1.0)
    iki_outlier_score: float = Field(default=0.0, ge=0.0, le=1.0)
    first_keypress_score: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_time_score: float = Field(default=0.0, ge=0.0, le=1.0)
    resize_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)


def compute_signal_scores(
    tab_blur_score: float = 0.0,
    paste_score: float = 0.0,
    iki_outlier_score: float = 0.0,
    first_keypress_score: float = 0.0,
    answer_time_score: float = 0.0,
    resize_score: float = 0.0,
) -> SignalScoreResult:
    """Pure function: combine six pre-computed component scores into a
    weighted composite risk score.

    Each input is expected to already be normalised to [0.0, 1.0] by the
    caller (e.g. tab_blur counting logic, IKI outlier detection, etc.).
    Missing components default to 0.0 — "no suspicion detected" rather than
    an error, since not every exam session will have produced every signal
    type (e.g. a student who never pasted anything has no paste events at
    all, which is itself non-suspicious).

    No database access, no network calls — this function is pure and can be
    tested entirely in isolation.
    """
    components = {
        "tab_blur_score": _clamp(tab_blur_score),
        "paste_score": _clamp(paste_score),
        "iki_outlier_score": _clamp(iki_outlier_score),
        "first_keypress_score": _clamp(first_keypress_score),
        "answer_time_score": _clamp(answer_time_score),
        "resize_score": _clamp(resize_score),
    }

    risk_score = _clamp(sum(WEIGHTS[key] * components[key] for key in WEIGHTS))

    return SignalScoreResult(**components, risk_score=risk_score)
