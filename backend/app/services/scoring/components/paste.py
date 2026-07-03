"""paste_score — AEGIS-54, single-large-paste tweak in AEGIS-104.

Scores paste behaviour per question: repeated pastes into the same question are
suspicious, and a large paste (>200 chars) adds a bonus. A single *small* paste
scores zero (it may be a trivial edit), but a single *large* paste now scores a
moderate 0.40: the client filters copy/paste that originates within the exam
(AEGIS-104), so a paste event reaching the scorer came from outside — a lone
large external paste is a real, if not conclusive, cheating signal. The session
score is the most suspicious single question, already normalised to 0–1.
Signal weight in the aggregate scorer: 0.25.
"""

from collections.abc import Iterable

from app.services.scoring import ScoringEvent

_LARGE_PASTE_CHARS = 200
_LARGE_PASTE_BONUS = 0.20
# A single large external paste is suspicious on its own but not conclusive.
_SINGLE_LARGE_PASTE_SCORE = 0.40


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
        large = any(c > _LARGE_PASTE_CHARS for c in char_counts)
        if pastes >= 3:
            score = min(1.0, 0.80 + (_LARGE_PASTE_BONUS if large else 0.0))
        elif pastes == 2:
            score = min(1.0, 0.50 + (_LARGE_PASTE_BONUS if large else 0.0))
        elif large:
            # A single large external paste is a real single-shot signal. The
            # 0.40 already reflects its size — no extra bonus on top.
            score = _SINGLE_LARGE_PASTE_SCORE
        else:
            # A single small paste scores 0.0 — likely a trivial/benign edit.
            continue
        best = max(best, score)
    return best
