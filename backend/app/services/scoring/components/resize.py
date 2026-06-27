"""resize_score — AEGIS-56.

Counts significant viewport-width changes — more than 20% off the first observed
width — which can indicate arranging a browser side-by-side with another window.
A +0.20 correlation bonus is added when tab-switching (tab_blur) is also present,
since resizing *and* leaving the tab together is more suspicious than either alone.

Reads ``resize`` events (payload ``width``) and ``tab_blur`` events; events are
assumed to be in chronological order, as provided by both callers. Weight: 0.05.
"""

from collections.abc import Iterable

from app.services.scoring import ScoringEvent

_SIGNIFICANT_WIDTH_CHANGE = 0.20
_TAB_BLUR_BONUS = 0.20


def resize_score(events: Iterable[ScoringEvent]) -> float:
    """Return a 0–1 score from significant resizes, with a tab_blur bonus."""
    baseline_width: float | None = None
    significant = 0
    has_tab_blur = False

    for event in events:
        if event.event_type == "tab_blur":
            has_tab_blur = True
        elif event.event_type == "resize":
            width = event.payload.get("width")
            if not isinstance(width, (int, float)):
                continue
            width = float(width)
            if baseline_width is None:
                baseline_width = width  # first resize sets the baseline viewport
            elif (
                baseline_width > 0
                and abs(width - baseline_width) / baseline_width
                > _SIGNIFICANT_WIDTH_CHANGE
            ):
                significant += 1

    if significant == 0:
        score = 0.0
    elif significant <= 2:
        score = 0.3
    else:
        score = 0.7

    if score > 0.0 and has_tab_blur:
        score = min(1.0, score + _TAB_BLUR_BONUS)
    return score
