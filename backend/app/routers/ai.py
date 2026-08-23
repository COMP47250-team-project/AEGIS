"""AI feature endpoints for AEGIS.

All endpoints are:
- Professor-only (require_role("professor") + exam ownership check).
- Closed-exam only (1B, 1C).
- Non-blocking: AI runs on-demand; nothing is auto-committed.
- Graceful: return a valid response even when AI is unavailable (stub mode).

Routes
------
GET  /ai/exams/{exam_id}/students/{student_id}/integrity-brief   — 1A
POST /ai/exams/{exam_id}/grade/suggest                           — 1B
GET  /ai/exams/{exam_id}/collusion                               — 1C
GET  /ai/status                                                  — health/provider info
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.exam import ExamAnswer, ExamSession, Enrollment
from app.models.quiz import Question
from app.models.telemetry import SessionScore, TelemetryEvent
from app.services.ai.client import get_ai_client
from app.services.ai.grading import AnswerToGrade, suggest_grades
from app.services.ai.narrative import (
    BriefResult,
    EventAggregates,
    ExamContext,
    ScoreSnapshot,
    build_integrity_brief,
)
from app.services.ai.similarity import AnswerToEmbed, detect_collusion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# Helpers (mirrors exams.py pattern)
# ---------------------------------------------------------------------------


async def _get_exam_or_404(db: AsyncSession, exam_id: uuid.UUID) -> ExamSession:
    result = await db.execute(select(ExamSession).where(ExamSession.id == exam_id))
    exam = result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found"
        )
    return exam


def _assert_owner(exam: ExamSession, user_id: str) -> None:
    if exam.created_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not the exam owner"
        )


def _assert_closed(exam: ExamSession) -> None:
    if exam.state != "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This operation is only available for closed exams",
        )


# ---------------------------------------------------------------------------
# GET /ai/status
# ---------------------------------------------------------------------------


class AIStatusResponse(BaseModel):
    provider: str
    ai_features_enabled: bool


@router.get("/status", response_model=AIStatusResponse)
async def ai_status() -> AIStatusResponse:
    """Return which AI backend is active (azure / ollama / stub)."""
    client = get_ai_client()
    from app.config import settings

    return AIStatusResponse(
        provider=client.provider.value,
        ai_features_enabled=settings.ai_features_enabled,
    )


# ---------------------------------------------------------------------------
# 1A — GET /ai/exams/{exam_id}/students/{student_id}/integrity-brief
# ---------------------------------------------------------------------------


class IntegrityBriefResponse(BaseModel):
    exam_id: uuid.UUID
    student_id: str
    brief: str
    provider: str
    contributors: list[str]


@router.get(
    "/exams/{exam_id}/students/{student_id}/integrity-brief",
    response_model=IntegrityBriefResponse,
)
async def get_integrity_brief(
    exam_id: uuid.UUID,
    student_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> IntegrityBriefResponse:
    """Generate a plain-English integrity brief for one student (metadata only)."""
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)

    # Load session score
    score_result = await db.execute(
        select(SessionScore).where(
            SessionScore.exam_id == exam_id,
            SessionScore.student_id == student_id,
        )
    )
    score_row = score_result.scalar_one_or_none()

    if score_row is None:
        # No score yet — return a stub brief rather than 404
        return IntegrityBriefResponse(
            exam_id=exam_id,
            student_id=student_id,
            brief=(
                "No integrity score has been computed for this student yet. "
                "Scores are computed after the exam closes."
            ),
            provider="none",
            contributors=[],
        )

    # Aggregate telemetry event counts (metadata only)
    events_result = await db.execute(
        select(TelemetryEvent.event_type).where(
            TelemetryEvent.exam_id == exam_id,
            TelemetryEvent.student_id == student_id,
        )
    )
    event_types = [row[0] for row in events_result.all()]
    event_counts: dict[str, int] = defaultdict(int)
    for et in event_types:
        event_counts[et] += 1

    # Load quiz context
    quiz_result = await db.execute(select(ExamSession).where(ExamSession.id == exam_id))
    # Count questions
    from app.models.quiz import Quiz

    quiz_q = await db.execute(select(Question).where(Question.quiz_id == exam.quiz_id))
    question_count = len(list(quiz_q.scalars().all()))

    scores = ScoreSnapshot(
        tab_switch_score=score_row.tab_switch_score,
        paste_score=score_row.paste_score,
        keystroke_score=score_row.keystroke_score,
        focus_loss_score=score_row.focus_loss_score,
        answer_timing_score=score_row.answer_timing_score,
        copy_sequence_score=score_row.copy_sequence_score,
        integrity_score=score_row.integrity_score,
    )
    events = EventAggregates(
        tab_blur_count=event_counts.get("tab_blur", 0),
        paste_count=event_counts.get("paste", 0),
        resize_count=event_counts.get("resize", 0),
        focus_loss_count=event_counts.get("focus_loss", 0),
    )
    context = ExamContext(
        duration_minutes=exam.duration_minutes,
        question_count=question_count,
        scoring_preset=exam.scoring_preset,
    )

    result: BriefResult = await build_integrity_brief(scores, events, context)

    return IntegrityBriefResponse(
        exam_id=exam_id,
        student_id=student_id,
        brief=result.brief,
        provider=result.provider,
        contributors=result.contributors,
    )


# ---------------------------------------------------------------------------
# 1B — POST /ai/exams/{exam_id}/grade/suggest
# ---------------------------------------------------------------------------


class GradeSuggestRequest(BaseModel):
    rubric: str | None = Field(None, max_length=1000)
    question_ids: list[uuid.UUID] | None = None  # None = all short answers


class GradeSuggestionItem(BaseModel):
    answer_id: uuid.UUID
    student_id: str
    question_id: uuid.UUID
    suggested_score: float | None
    rationale: str
    confidence: float
    max_score: int


class GradeSuggestResponse(BaseModel):
    exam_id: uuid.UUID
    suggestions: list[GradeSuggestionItem]
    provider: str


@router.post(
    "/exams/{exam_id}/grade/suggest",
    response_model=GradeSuggestResponse,
)
async def suggest_exam_grades(
    exam_id: uuid.UUID,
    body: GradeSuggestRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> GradeSuggestResponse:
    """Suggest scores for all (or selected) short answers in a closed exam.

    Does NOT write any scores — acceptance uses the existing
    PATCH /exams/{exam_id}/answers/grade endpoint.
    """
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)
    _assert_closed(exam)

    # Load short-answer questions
    q_result = await db.execute(
        select(Question).where(
            Question.quiz_id == exam.quiz_id,
            Question.type == "short",
        )
    )
    questions = list(q_result.scalars().all())
    if body.question_ids:
        questions = [q for q in questions if q.id in set(body.question_ids)]

    if not questions:
        return GradeSuggestResponse(
            exam_id=exam_id, suggestions=[], provider=get_ai_client().provider.value
        )

    question_map = {q.id: q for q in questions}

    # Load all short answers for these questions
    answer_result = await db.execute(
        select(ExamAnswer).where(
            ExamAnswer.exam_id == exam_id,
            ExamAnswer.question_id.in_(list(question_map.keys())),
        )
    )
    answers = list(answer_result.scalars().all())

    if not answers:
        return GradeSuggestResponse(
            exam_id=exam_id, suggestions=[], provider=get_ai_client().provider.value
        )

    # Build grading items
    items = [
        AnswerToGrade(
            answer_id=ans.id,
            question_prompt=question_map[ans.question_id].prompt,
            student_answer=ans.answer,
            model_answer=question_map[ans.question_id].correct_answer,
            max_score=question_map[ans.question_id].max_score,
        )
        for ans in answers
        if ans.question_id in question_map
    ]

    suggestions = await suggest_grades(items, rubric=body.rubric)

    # Map answer_id -> student_id + question_id for the response
    answer_meta = {ans.id: ans for ans in answers}
    client = get_ai_client()

    return GradeSuggestResponse(
        exam_id=exam_id,
        provider=client.provider.value,
        suggestions=[
            GradeSuggestionItem(
                answer_id=s.answer_id,
                student_id=answer_meta[s.answer_id].student_id,
                question_id=answer_meta[s.answer_id].question_id,
                suggested_score=s.suggested_score,
                rationale=s.rationale,
                confidence=s.confidence,
                max_score=question_map[answer_meta[s.answer_id].question_id].max_score,
            )
            for s in suggestions
            if s.answer_id in answer_meta
        ],
    )


# ---------------------------------------------------------------------------
# 1C — GET /ai/exams/{exam_id}/collusion
# ---------------------------------------------------------------------------


class SimilarPairItem(BaseModel):
    question_id: uuid.UUID
    student_a: str
    student_b: str
    answer_id_a: uuid.UUID
    answer_id_b: uuid.UUID
    similarity: float


class CollusionResponse(BaseModel):
    exam_id: uuid.UUID
    flagged_pairs: list[SimilarPairItem]
    matrix: dict[str, dict[str, dict[str, float]]]
    provider: str
    threshold_used: float
    pair_count: int


@router.get(
    "/exams/{exam_id}/collusion",
    response_model=CollusionResponse,
)
async def get_collusion_report(
    exam_id: uuid.UUID,
    threshold: float = DEFAULT_THRESHOLD,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> CollusionResponse:
    """Compute pairwise answer similarity and return flagged pairs.

    Runs on-demand; results are not cached (re-running is idempotent).
    """
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)
    _assert_closed(exam)

    # Load short-answer questions
    q_result = await db.execute(
        select(Question).where(
            Question.quiz_id == exam.quiz_id,
            Question.type == "short",
        )
    )
    short_question_ids = {q.id for q in q_result.scalars().all()}

    if not short_question_ids:
        return CollusionResponse(
            exam_id=exam_id,
            flagged_pairs=[],
            matrix={},
            provider=get_ai_client().provider.value,
            threshold_used=threshold,
            pair_count=0,
        )

    # Load all short answers
    answer_result = await db.execute(
        select(ExamAnswer).where(
            ExamAnswer.exam_id == exam_id,
            ExamAnswer.question_id.in_(list(short_question_ids)),
        )
    )
    answers = list(answer_result.scalars().all())

    items = [
        AnswerToEmbed(
            answer_id=ans.id,
            student_id=ans.student_id,
            question_id=ans.question_id,
            answer_text=ans.answer,
        )
        for ans in answers
    ]

    result = await detect_collusion(items, threshold=threshold)

    return CollusionResponse(
        exam_id=exam_id,
        flagged_pairs=[
            SimilarPairItem(
                question_id=p.question_id,
                student_a=p.student_a,
                student_b=p.student_b,
                answer_id_a=p.answer_id_a,
                answer_id_b=p.answer_id_b,
                similarity=p.similarity,
            )
            for p in result.flagged_pairs
        ],
        matrix=result.matrix,
        provider=result.provider,
        threshold_used=result.threshold_used,
        pair_count=len(result.flagged_pairs),
    )


# Import DEFAULT_THRESHOLD for the route default
from app.services.ai.similarity import DEFAULT_THRESHOLD  # noqa: E402
