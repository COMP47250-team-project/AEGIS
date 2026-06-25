"""paste_score — AEGIS-54.

Scores paste behaviour per question: repeated pastes into the same question are
suspicious, and a large paste (>200 chars) adds a bonus. A single paste scores
zero — it may just be the student copying the question text. The session score
is the most suspicious single question, so it is already normalised to 0–1.
Signal weight in the aggregate scorer: 0.25.
"""

from collections.abc import Iterable

from app.services.scoring import ScoringEvent

_LARGE_PASTE_CHARS = 200
_LARGE_PASTE_BONUS = 0.20


def paste_score(events: Iterable[ScoringEvent]) -> float:
    """Return a 0–1 paste risk sub-score for one session's events."""
    char_counts_by_question: dict[object, list[int]] = {}
    for event in events:
        if event.event_type != "paste":
            continue
        question_id = event.payload.get("question_id")
        raw = event.payload.get("char_count")
        char_count = int(raw) if isinstance(raw, (int, float)) else 0
        char_counts_by_question.setdefault(question_id, []).append(char_count)

    best = 0.0
    for char_counts in char_counts_by_question.values():
        pastes = len(char_counts)
        if pastes >= 3:
            base = 0.80
        elif pastes == 2:
            base = 0.50
        else:
            # A single paste scores 0.0 — it may just be the student copying the
            # (often long) question text, so the size bonus does not apply here.
            best = max(best, 0.0)
            continue
        bonus = (
            _LARGE_PASTE_BONUS
            if any(c > _LARGE_PASTE_CHARS for c in char_counts)
            else 0.0
        )
        best = max(best, min(1.0, base + bonus))
    return best
