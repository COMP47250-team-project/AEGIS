"""1A — AI Integrity Brief.

Generates a plain-English, evidence-cited summary of a flagged student's
behaviour from the six signal sub-scores and aggregated telemetry event counts.

Privacy guarantee: only metadata (counts, scores, timings) is sent to the
model — never keystroke content, clipboard text, or answer text.

The brief always ends with a non-verdict disclaimer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.services.ai.client import AIProvider, get_ai_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data shapes (plain dataclasses — no ORM dependency here)
# ---------------------------------------------------------------------------


@dataclass
class ScoreSnapshot:
    """The six sub-scores and aggregate from session_scores."""

    tab_switch_score: float
    paste_score: float
    keystroke_score: float
    focus_loss_score: float
    answer_timing_score: float
    copy_sequence_score: float
    integrity_score: float


@dataclass
class EventAggregates:
    """Aggregated telemetry event counts/timings — metadata only."""

    tab_blur_count: int = 0
    paste_count: int = 0
    resize_count: int = 0
    focus_loss_count: int = 0
    # Which question positions had the most tab-blur events (top-3)
    top_blur_questions: list[int] | None = None


@dataclass
class ExamContext:
    duration_minutes: int
    question_count: int
    scoring_preset: str  # strict | standard | lenient


@dataclass
class BriefResult:
    brief: str
    provider: str  # "azure" | "ollama" | "stub"
    contributors: list[str]  # signal names that drove the score


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an academic integrity assistant for a university exam portal called AEGIS.
Your role is to help professors understand a student's behavioural signals during an exam.

Rules you must follow without exception:
1. Base your summary ONLY on the numbers provided — do not invent facts.
2. Keep the summary to 3-5 sentences, under 120 words.
3. Name the specific signals that contributed most (tab switches, paste events, keystroke rhythm, etc.).
4. Use neutral, factual language. Do not assert that the student cheated.
5. End EVERY response with exactly this sentence on its own line:
   "This is an AI-generated summary for human review — it is not a verdict and does not constitute evidence of academic misconduct."
6. Do not include any other disclaimer or preamble.
"""

_USER_TEMPLATE = """\
Exam context:
- Duration: {duration_minutes} minutes
- Questions: {question_count}
- Scoring preset: {scoring_preset}

Signal sub-scores (0 = no concern, 1 = maximum concern):
- Tab switches:      {tab_switch_score:.2f}
- Paste events:      {paste_score:.2f}
- Keystroke rhythm:  {keystroke_score:.2f}
- Focus loss:        {focus_loss_score:.2f}
- Answer timing:     {answer_timing_score:.2f}
- Window resize:     {copy_sequence_score:.2f}
- AGGREGATE score:   {integrity_score:.2f}

Telemetry event counts:
- Tab blur events:   {tab_blur_count}
- Paste events:      {paste_count}
- Focus loss events: {focus_loss_count}
- Resize events:     {resize_count}
{top_blur_line}

Write the integrity brief now.
"""


def _build_contributors(scores: ScoreSnapshot) -> list[str]:
    """Return the top-2 signal names by sub-score value."""
    ranked = sorted(
        [
            ("tab switches", scores.tab_switch_score),
            ("paste events", scores.paste_score),
            ("keystroke rhythm", scores.keystroke_score),
            ("focus loss", scores.focus_loss_score),
            ("answer timing", scores.answer_timing_score),
            ("window resize", scores.copy_sequence_score),
        ],
        key=lambda x: x[1],
        reverse=True,
    )
    return [name for name, score in ranked[:2] if score > 0.05]


async def build_integrity_brief(
    scores: ScoreSnapshot,
    events: EventAggregates,
    context: ExamContext,
) -> BriefResult:
    """Generate the integrity brief for one student.

    Returns a BriefResult regardless of which backend is active.
    Falls back gracefully if the AI call fails.
    """
    contributors = _build_contributors(scores)

    top_blur_line = ""
    if events.top_blur_questions:
        qs = ", ".join(f"Q{q}" for q in events.top_blur_questions[:3])
        top_blur_line = f"- Tab blurs concentrated on: {qs}"

    user_msg = _USER_TEMPLATE.format(
        duration_minutes=context.duration_minutes,
        question_count=context.question_count,
        scoring_preset=context.scoring_preset,
        tab_switch_score=scores.tab_switch_score,
        paste_score=scores.paste_score,
        keystroke_score=scores.keystroke_score,
        focus_loss_score=scores.focus_loss_score,
        answer_timing_score=scores.answer_timing_score,
        copy_sequence_score=scores.copy_sequence_score,
        integrity_score=scores.integrity_score,
        tab_blur_count=events.tab_blur_count,
        paste_count=events.paste_count,
        focus_loss_count=events.focus_loss_count,
        resize_count=events.resize_count,
        top_blur_line=top_blur_line,
    )

    client = get_ai_client()

    if client.provider == AIProvider.STUB:
        brief = _stub_brief(scores, events, context)
        return BriefResult(brief=brief, provider="stub", contributors=contributors)

    try:
        brief = await client.chat(
            system=_SYSTEM_PROMPT,
            user=user_msg,
            temperature=0.0,
            max_tokens=200,
        )
    except Exception:
        logger.exception("AI brief generation failed — returning stub")
        brief = _stub_brief(scores, events, context)
        return BriefResult(brief=brief, provider="stub", contributors=contributors)

    return BriefResult(
        brief=brief.strip(),
        provider=client.provider.value,
        contributors=contributors,
    )


def _stub_brief(
    scores: ScoreSnapshot,
    events: EventAggregates,
    context: ExamContext,
) -> str:
    """Deterministic template-based brief used when no AI backend is available."""
    top = _build_contributors(scores)
    top_str = " and ".join(top) if top else "no dominant signals"
    return (
        f"[AI unavailable — template summary] "
        f"During the {context.duration_minutes}-minute exam this student recorded "
        f"an aggregate integrity score of {scores.integrity_score:.2f}. "
        f"The main contributing signals were {top_str} "
        f"({events.tab_blur_count} tab-blur event(s), {events.paste_count} paste event(s)). "
        f"Manual review is recommended for answers with high sub-scores. "
        f"This is an AI-generated summary for human review — it is not a verdict "
        f"and does not constitute evidence of academic misconduct."
    )
