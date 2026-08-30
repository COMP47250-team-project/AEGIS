"""1C — Answer-Similarity / Collusion Detection.

Embeds every student's short answers, computes pairwise cosine similarity
per question, and flags suspiciously similar answer pairs across students.

This is a content-based integrity dimension independent of behavioural
telemetry.  Results are evidence for human review, not proof of misconduct.

Local twin: Ollama nomic-embed-text (same code path, different base_url).
Fallback: if embeddings are unavailable the feature returns an empty result
rather than raising, so the rest of the report is unaffected.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

import numpy as np

from app.services.ai.client import AIProvider, get_ai_client

logger = logging.getLogger(__name__)

# Cosine similarity threshold above which a pair is flagged.
# 0.92 is conservative — identical phrasing of a short factual answer
# (e.g. "photosynthesis") will score ~1.0 but is expected; tune per exam.
DEFAULT_THRESHOLD = 0.92

# Minimum answer length (chars) to embed — skip trivially short answers.
MIN_ANSWER_LENGTH = 20


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass
class AnswerToEmbed:
    answer_id: uuid.UUID
    student_id: str
    question_id: uuid.UUID
    answer_text: str


@dataclass
class SimilarPair:
    question_id: uuid.UUID
    student_a: str
    student_b: str
    answer_id_a: uuid.UUID
    answer_id_b: uuid.UUID
    similarity: float  # 0.0–1.0


@dataclass
class CollusionResult:
    flagged_pairs: list[SimilarPair] = field(default_factory=list)
    # Per-question matrix: {question_id: {student_id: {student_id: similarity}}}
    matrix: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    provider: str = "stub"
    threshold_used: float = DEFAULT_THRESHOLD


# ---------------------------------------------------------------------------
# Cosine similarity (pure numpy — no external ML library needed)
# ---------------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


async def detect_collusion(
    answers: list[AnswerToEmbed],
    threshold: float = DEFAULT_THRESHOLD,
) -> CollusionResult:
    """Embed answers and return flagged similar pairs.

    Groups answers by question so that per-question similarity is computed
    independently (avoids cross-question false positives).

    Returns an empty CollusionResult (not an error) when:
    - AI features are disabled / stub mode
    - No short answers exist
    - Embedding call fails
    """
    if not answers:
        return CollusionResult()

    client = get_ai_client()

    if client.provider == AIProvider.STUB:
        logger.info("Collusion detection: AI stub active — returning empty result")
        return CollusionResult(provider="stub", threshold_used=threshold)

    # Group by question
    by_question: dict[uuid.UUID, list[AnswerToEmbed]] = {}
    for ans in answers:
        if len(ans.answer_text.strip()) < MIN_ANSWER_LENGTH:
            continue
        by_question.setdefault(ans.question_id, []).append(ans)

    if not by_question:
        return CollusionResult(provider=client.provider.value, threshold_used=threshold)

    flagged: list[SimilarPair] = []
    matrix: dict[str, dict[str, dict[str, float]]] = {}

    for question_id, q_answers in by_question.items():
        if len(q_answers) < 2:
            continue

        texts = [a.answer_text for a in q_answers]
        try:
            vectors = await client.embed(texts)
        except Exception:
            logger.exception("Embedding failed for question %s — skipping", question_id)
            continue

        qid_str = str(question_id)
        matrix[qid_str] = {}

        # Pairwise comparison
        for i in range(len(q_answers)):
            si = q_answers[i].student_id
            matrix[qid_str].setdefault(si, {})
            for j in range(i + 1, len(q_answers)):
                sj = q_answers[j].student_id
                matrix[qid_str].setdefault(sj, {})

                sim = _cosine_similarity(vectors[i], vectors[j])
                matrix[qid_str][si][sj] = round(sim, 4)
                matrix[qid_str][sj][si] = round(sim, 4)

                if sim >= threshold:
                    flagged.append(
                        SimilarPair(
                            question_id=question_id,
                            student_a=si,
                            student_b=sj,
                            answer_id_a=q_answers[i].answer_id,
                            answer_id_b=q_answers[j].answer_id,
                            similarity=round(sim, 4),
                        )
                    )

    # Sort by similarity descending
    flagged.sort(key=lambda p: p.similarity, reverse=True)

    return CollusionResult(
        flagged_pairs=flagged,
        matrix=matrix,
        provider=client.provider.value,
        threshold_used=threshold,
    )
