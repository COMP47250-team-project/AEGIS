"""first_keypress_score — AEGIS-56.

Flags an implausibly fast start: the time-to-first-keypress (ttfk), i.e. the
seconds from the exam/question being shown to the student's first keystroke.
A first keypress within 10s suggests a prepared or pre-typed answer.

Reads the first ``answer_start`` event (which carries ``elapsed_ms``); events are
assumed to be in chronological order, as provided by both callers. Weight: 0.10.
"""

from collections.abc import Iterable

from app.services.scoring import ScoringEvent

_FAST_TTFK_S = 10.0


def first_keypress_score(events: Iterable[ScoringEvent]) -> float:
    """Return 0.2 if the first keypress lands within 10s of start, else 0.0."""
    for event in events:
        if event.event_type == "answer_start":
            elapsed_ms = event.payload.get("elapsed_ms")
            if isinstance(elapsed_ms, (int, float)):
                return 0.2 if float(elapsed_ms) / 1000.0 < _FAST_TTFK_S else 0.0
    return 0.0
