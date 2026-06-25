"""tab_blur_score — AEGIS-54.

Counts distinct ``tab_blur`` events in a session and maps the (duration-weighted)
count to a 0–1 risk sub-score. A short blur (<2s away before returning) counts
half: a brief focus flicker is far less suspicious than leaving the exam for a
while. Signal weight in the aggregate scorer: 0.30.
"""

from collections.abc import Iterable

from app.services.scoring import ScoringEvent

# Time away (ms) below which a blur is treated as incidental and weighted 0.5x.
_SHORT_BLUR_MS = 2000.0

# (effective blur count -> score) anchor points. We linearly interpolate between
# them; past 4 the score rises +0.05 per extra blur, capped at 1.0.
_ANCHORS = ((0.0, 0.0), (1.0, 0.15), (2.0, 0.35), (3.0, 0.60), (4.0, 0.85))


def _score_from_count(count: float) -> float:
    if count <= 0.0:
        return 0.0
    for (x0, y0), (x1, y1) in zip(_ANCHORS, _ANCHORS[1:]):
        if count <= x1:
            return y0 + (count - x0) / (x1 - x0) * (y1 - y0)
    return min(1.0, 0.85 + 0.05 * (count - 4.0))


def tab_blur_score(events: Iterable[ScoringEvent]) -> float:
    """Return a 0–1 tab-switching risk sub-score for one session's events."""
    blur_count = 0
    away_durations: list[float] = []
    for event in events:
        if event.event_type == "tab_blur":
            blur_count += 1
        elif event.event_type == "tab_return":
            duration = event.payload.get("duration_away_ms")
            if isinstance(duration, (int, float)):
                away_durations.append(float(duration))

    if blur_count == 0:
        return 0.0

    # Pair each blur with a known return duration to weight it; any blur with no
    # recorded return (still away at session end) counts at full weight.
    matched = min(len(away_durations), blur_count)
    effective = sum(0.5 if d < _SHORT_BLUR_MS else 1.0 for d in away_durations[:matched])
    effective += float(blur_count - matched)
    return _score_from_count(effective)
