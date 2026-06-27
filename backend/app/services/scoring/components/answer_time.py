"""answer_time_distribution_score — AEGIS-56.

Uneven time across questions (a high coefficient of variation) can indicate
copy-pasted answers on some questions while others take normal effort. A +0.20
bonus is added when an exam with more than 5 questions has any question answered
in under 30s.

Reads ``question_time`` events, whose ``duration_ms`` is cumulative per question
(largest value seen wins). Weight: 0.10.
"""

import math
from collections.abc import Iterable

from app.services.scoring import ScoringEvent

_CV_WEIGHT = 0.8
_MIN_QUESTIONS_FOR_FLAG = 5
_SHORT_ANSWER_MS = 30_000.0
_SHORT_ANSWER_BONUS = 0.20


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def answer_time_distribution_score(events: Iterable[ScoringEvent]) -> float:
    """Return a 0–1 score from the spread of per-question answer times."""
    durations: dict[object, float] = {}
    total_questions = 0
    for event in events:
        if event.event_type != "question_time":
            continue
        duration = event.payload.get("duration_ms")
        if isinstance(duration, (int, float)):
            qid = event.payload.get("question_id")
            durations[qid] = max(durations.get(qid, 0.0), float(duration))
        declared = event.payload.get("total_questions")
        if isinstance(declared, (int, float)):
            total_questions = max(total_questions, int(declared))

    if not durations:
        return 0.0

    values = list(durations.values())
    mean = sum(values) / len(values)
    if mean <= 0.0:
        return 0.0

    std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    score = (std / mean) * _CV_WEIGHT

    # Long exam with at least one very fast question → add a bonus.
    exam_length = total_questions or len(values)
    if exam_length > _MIN_QUESTIONS_FOR_FLAG and any(
        v < _SHORT_ANSWER_MS for v in values
    ):
        score += _SHORT_ANSWER_BONUS

    return _clamp(score)
