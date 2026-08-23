"""Tests for the AI services layer (1A narrative, 1B grading, 1C similarity).

All tests run without any Azure or Ollama credentials — the dev stub is used.
This ensures CI stays green with no external dependencies.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.client import AIProvider, get_ai_client
from app.services.ai.grading import AnswerToGrade, GradeSuggestion, suggest_grades
from app.services.ai.narrative import (
    BriefResult,
    EventAggregates,
    ExamContext,
    ScoreSnapshot,
    build_integrity_brief,
)
from app.services.ai.similarity import AnswerToEmbed, CollusionResult, detect_collusion


# ---------------------------------------------------------------------------
# Client resolver
# ---------------------------------------------------------------------------


def test_get_ai_client_returns_stub_when_no_env(monkeypatch):
    """With no Azure or Ollama env vars, the factory returns the dev stub."""
    # Clear the lru_cache so the factory re-evaluates
    get_ai_client.cache_clear()
    monkeypatch.setattr("app.config.settings.azure_openai_endpoint", None)
    monkeypatch.setattr("app.config.settings.azure_openai_api_key", None)
    monkeypatch.setattr("app.config.settings.ollama_base_url", None)
    client = get_ai_client()
    assert client.provider == AIProvider.STUB
    get_ai_client.cache_clear()


def test_get_ai_client_returns_stub_when_disabled(monkeypatch):
    get_ai_client.cache_clear()
    monkeypatch.setattr("app.config.settings.ai_features_enabled", False)
    client = get_ai_client()
    assert client.provider == AIProvider.STUB
    get_ai_client.cache_clear()


# ---------------------------------------------------------------------------
# 1A — Narrative (stub path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_integrity_brief_stub():
    """build_integrity_brief returns a BriefResult even with the stub client."""
    get_ai_client.cache_clear()
    scores = ScoreSnapshot(
        tab_switch_score=0.8,
        paste_score=0.9,
        keystroke_score=0.3,
        focus_loss_score=0.1,
        answer_timing_score=0.5,
        copy_sequence_score=0.05,
        integrity_score=0.72,
    )
    events = EventAggregates(
        tab_blur_count=4, paste_count=2, resize_count=0, focus_loss_count=1
    )
    context = ExamContext(
        duration_minutes=60, question_count=5, scoring_preset="standard"
    )

    result = await build_integrity_brief(scores, events, context)

    assert isinstance(result, BriefResult)
    assert len(result.brief) > 20
    assert "not a verdict" in result.brief.lower()
    assert result.provider in ("stub", "azure", "ollama")


@pytest.mark.asyncio
async def test_build_integrity_brief_uses_ai_client():
    """build_integrity_brief calls client.chat and returns its output."""
    get_ai_client.cache_clear()
    fake_brief = (
        "Student switched tabs 4 times. "
        "This is an AI-generated summary for human review — "
        "it is not a verdict and does not constitute evidence of academic misconduct."
    )
    mock_client = AsyncMock()
    mock_client.provider = AIProvider.AZURE
    mock_client.chat = AsyncMock(return_value=fake_brief)

    with patch("app.services.ai.narrative.get_ai_client", return_value=mock_client):
        scores = ScoreSnapshot(0.8, 0.9, 0.3, 0.1, 0.5, 0.05, 0.72)
        events = EventAggregates(4, 2, 0, 1)
        context = ExamContext(60, 5, "standard")
        result = await build_integrity_brief(scores, events, context)

    assert result.brief == fake_brief
    assert result.provider == "azure"
    mock_client.chat.assert_called_once()


# ---------------------------------------------------------------------------
# 1B — Grading (stub path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggest_grades_stub_returns_none_scores():
    """With the stub, suggested_score is None and rationale mentions 'unavailable'."""
    get_ai_client.cache_clear()
    items = [
        AnswerToGrade(
            answer_id=uuid.uuid4(),
            question_prompt="Explain photosynthesis.",
            student_answer="Plants use sunlight to make food.",
            model_answer="Photosynthesis converts CO2 and water into glucose using light energy.",
            max_score=5,
        )
    ]
    suggestions = await suggest_grades(items)
    assert len(suggestions) == 1
    s = suggestions[0]
    assert isinstance(s, GradeSuggestion)
    assert s.suggested_score is None
    assert "unavailable" in s.rationale.lower() or "stub" in s.rationale.lower()


@pytest.mark.asyncio
async def test_suggest_grades_parses_valid_json():
    """suggest_grades correctly parses a well-formed JSON response."""
    get_ai_client.cache_clear()
    answer_id = uuid.uuid4()
    items = [
        AnswerToGrade(
            answer_id=answer_id,
            question_prompt="What is 2+2?",
            student_answer="4",
            model_answer="4",
            max_score=2,
        )
    ]
    mock_client = AsyncMock()
    mock_client.provider = AIProvider.AZURE
    mock_client.chat = AsyncMock(
        return_value='{"score": 2, "rationale": "Correct answer.", "confidence": 0.99}'
    )

    with patch("app.services.ai.grading.get_ai_client", return_value=mock_client):
        suggestions = await suggest_grades(items)

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.suggested_score == 2.0
    assert s.confidence == 0.99
    assert "Correct" in s.rationale


@pytest.mark.asyncio
async def test_suggest_grades_clamps_score():
    """suggest_grades clamps a score that exceeds max_score."""
    get_ai_client.cache_clear()
    answer_id = uuid.uuid4()
    items = [
        AnswerToGrade(
            answer_id=answer_id,
            question_prompt="Q",
            student_answer="A",
            model_answer="A",
            max_score=3,
        )
    ]
    mock_client = AsyncMock()
    mock_client.provider = AIProvider.AZURE
    mock_client.chat = AsyncMock(
        return_value='{"score": 99, "rationale": "Over-scored.", "confidence": 0.5}'
    )

    with patch("app.services.ai.grading.get_ai_client", return_value=mock_client):
        suggestions = await suggest_grades(items)

    assert suggestions[0].suggested_score == 3.0  # clamped to max_score


@pytest.mark.asyncio
async def test_suggest_grades_empty_input():
    suggestions = await suggest_grades([])
    assert suggestions == []


# ---------------------------------------------------------------------------
# 1C — Similarity (stub path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_collusion_stub_returns_empty():
    """With the stub, detect_collusion returns an empty result (not an error)."""
    get_ai_client.cache_clear()
    items = [
        AnswerToEmbed(
            answer_id=uuid.uuid4(),
            student_id="s1",
            question_id=uuid.uuid4(),
            answer_text="Photosynthesis is the process by which plants make food.",
        )
    ]
    result = await detect_collusion(items)
    assert isinstance(result, CollusionResult)
    assert result.flagged_pairs == []
    assert result.provider == "stub"


@pytest.mark.asyncio
async def test_detect_collusion_flags_similar_answers():
    """detect_collusion flags a pair with cosine similarity above the threshold."""
    get_ai_client.cache_clear()
    qid = uuid.uuid4()
    aid1, aid2 = uuid.uuid4(), uuid.uuid4()
    items = [
        AnswerToEmbed(
            aid1, "s1", qid, "Photosynthesis converts sunlight into glucose."
        ),
        AnswerToEmbed(
            aid2, "s2", qid, "Photosynthesis converts sunlight into glucose."
        ),
    ]
    # Return near-identical vectors so cosine similarity ≈ 1.0
    vec = [1.0, 0.0, 0.0]
    mock_client = AsyncMock()
    mock_client.provider = AIProvider.AZURE
    mock_client.embed = AsyncMock(return_value=[vec, vec])

    with patch("app.services.ai.similarity.get_ai_client", return_value=mock_client):
        result = await detect_collusion(items, threshold=0.90)

    assert len(result.flagged_pairs) == 1
    pair = result.flagged_pairs[0]
    assert pair.similarity >= 0.90
    assert {pair.student_a, pair.student_b} == {"s1", "s2"}


@pytest.mark.asyncio
async def test_detect_collusion_does_not_flag_dissimilar():
    """detect_collusion does not flag orthogonal vectors."""
    get_ai_client.cache_clear()
    qid = uuid.uuid4()
    items = [
        AnswerToEmbed(
            uuid.uuid4(), "s1", qid, "Photosynthesis is a biological process."
        ),
        AnswerToEmbed(uuid.uuid4(), "s2", qid, "The French Revolution began in 1789."),
    ]
    mock_client = AsyncMock()
    mock_client.provider = AIProvider.AZURE
    mock_client.embed = AsyncMock(return_value=[[1.0, 0.0], [0.0, 1.0]])

    with patch("app.services.ai.similarity.get_ai_client", return_value=mock_client):
        result = await detect_collusion(items, threshold=0.90)

    assert result.flagged_pairs == []


@pytest.mark.asyncio
async def test_detect_collusion_skips_short_answers():
    """Answers shorter than MIN_ANSWER_LENGTH are skipped."""
    get_ai_client.cache_clear()
    qid = uuid.uuid4()
    items = [
        AnswerToEmbed(uuid.uuid4(), "s1", qid, "Yes"),  # too short
        AnswerToEmbed(uuid.uuid4(), "s2", qid, "No"),  # too short
    ]
    mock_client = AsyncMock()
    mock_client.provider = AIProvider.AZURE
    mock_client.embed = AsyncMock(return_value=[])

    with patch("app.services.ai.similarity.get_ai_client", return_value=mock_client):
        result = await detect_collusion(items)

    assert result.flagged_pairs == []
    mock_client.embed.assert_not_called()
