"""1B — AI-Assisted Short-Answer Grading.

Suggests a score, one-line rationale, and confidence for each short-answer
submission.  The professor reviews and accepts or overrides; nothing is
auto-committed.  Acceptance reuses the existing PATCH /exams/{id}/answers/grade
endpoint (ManualGradeSubmit).

Privacy: answer text is already stored and visible to the professor.
Azure OpenAI does not train on customer data.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass

from app.services.ai.client import AIProvider, get_ai_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass
class AnswerToGrade:
    answer_id: uuid.UUID
    question_prompt: str
    student_answer: str
    model_answer: str | None  # Question.correct_answer (nullable)
    max_score: int


@dataclass
class GradeSuggestion:
    answer_id: uuid.UUID
    suggested_score: float | None  # None when AI unavailable
    rationale: str
    confidence: float  # 0.0–1.0; 0.0 when unavailable


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a fair and consistent academic grader for a university exam portal.
Your task is to suggest a score for a student's short-answer response.

Rules:
1. Score strictly between 0 and max_score (inclusive). Use whole or half marks only.
2. Base your score ONLY on the provided question, model answer (if given), and student answer.
3. Be concise: one sentence rationale, max 20 words.
4. Respond with ONLY valid JSON in this exact format (no markdown, no extra keys):
   {"score": <number>, "rationale": "<string>", "confidence": <0.0-1.0>}
5. If the student answer is blank or clearly off-topic, score 0.
6. confidence reflects how certain you are: 1.0 = very clear, 0.5 = borderline.
"""

_USER_TEMPLATE = """\
Question: {question_prompt}
Model answer: {model_answer}
Student answer: {student_answer}
Max score: {max_score}
"""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _parse_suggestion(
    raw: str, answer_id: uuid.UUID, max_score: int
) -> GradeSuggestion:
    """Parse the JSON response; clamp score; fall back gracefully on parse error."""
    try:
        # Strip markdown code fences if the model wraps the JSON
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        data = json.loads(cleaned)
        score = float(data["score"])
        score = max(0.0, min(float(max_score), score))
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        rationale = str(data.get("rationale", "")).strip()[:200]
        return GradeSuggestion(
            answer_id=answer_id,
            suggested_score=score,
            rationale=rationale or "No rationale provided.",
            confidence=confidence,
        )
    except Exception:
        logger.warning("Failed to parse grading response: %r", raw[:200])
        return GradeSuggestion(
            answer_id=answer_id,
            suggested_score=None,
            rationale="AI response could not be parsed — please grade manually.",
            confidence=0.0,
        )


async def suggest_grades(
    items: list[AnswerToGrade],
    rubric: str | None = None,
) -> list[GradeSuggestion]:
    """Return one GradeSuggestion per AnswerToGrade item.

    Calls the AI backend once per answer (sequential to avoid rate-limit bursts).
    Falls back to a stub suggestion on any per-answer failure.
    """
    if not items:
        return []

    client = get_ai_client()

    if client.provider == AIProvider.STUB:
        return [_stub_suggestion(item) for item in items]

    system = _SYSTEM_PROMPT
    if rubric:
        system += f"\n\nAdditional rubric from the professor:\n{rubric}"

    results: list[GradeSuggestion] = []
    for item in items:
        model_answer_text = item.model_answer or "(no model answer provided)"
        user_msg = _USER_TEMPLATE.format(
            question_prompt=item.question_prompt,
            model_answer=model_answer_text,
            student_answer=item.student_answer or "(blank)",
            max_score=item.max_score,
        )
        try:
            raw = await client.chat(
                system=system,
                user=user_msg,
                temperature=0.0,
                max_tokens=120,
                response_format={"type": "json_object"},
            )
            results.append(_parse_suggestion(raw, item.answer_id, item.max_score))
        except Exception:
            logger.exception("Grading call failed for answer %s", item.answer_id)
            results.append(
                GradeSuggestion(
                    answer_id=item.answer_id,
                    suggested_score=None,
                    rationale="AI call failed — please grade manually.",
                    confidence=0.0,
                )
            )

    return results


def _stub_suggestion(item: AnswerToGrade) -> GradeSuggestion:
    return GradeSuggestion(
        answer_id=item.answer_id,
        suggested_score=None,
        rationale="[AI unavailable] No credentials configured — please grade manually.",
        confidence=0.0,
    )
