# backend/tests/test_auto_close.py
# AEGIS-115 Part A: regression tests for auto-close on duration expiry.

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.exam_scheduling import auto_close_if_expired, is_expired


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_exam(state="open", minutes_ago=70, duration=60):
    """Return a mock ExamSession that started `minutes_ago` minutes ago
    with a duration of `duration` minutes."""
    exam = MagicMock()
    exam.state = state
    exam.duration_minutes = duration
    start = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    exam.scheduled_start = start
    exam.id = "exam-test-id"
    exam.closed_at = None
    return exam


# ---------------------------------------------------------------------------
# is_expired — pure logic, no DB
# ---------------------------------------------------------------------------

def test_is_expired_returns_true_when_duration_elapsed():
    exam = make_exam(state="open", minutes_ago=70, duration=60)
    now = datetime.now(timezone.utc)
    assert is_expired(exam, now) is True


def test_is_expired_returns_false_when_still_running():
    exam = make_exam(state="open", minutes_ago=30, duration=60)
    now = datetime.now(timezone.utc)
    assert is_expired(exam, now) is False


def test_is_expired_returns_false_for_non_open_exam():
    exam = make_exam(state="draft", minutes_ago=70, duration=60)
    now = datetime.now(timezone.utc)
    assert is_expired(exam, now) is False


def test_is_expired_returns_false_when_no_scheduled_start():
    exam = make_exam(state="open", minutes_ago=70, duration=60)
    exam.scheduled_start = None
    now = datetime.now(timezone.utc)
    assert is_expired(exam, now) is False


def test_is_expired_returns_false_when_no_duration():
    exam = make_exam(state="open", minutes_ago=70, duration=60)
    exam.duration_minutes = None
    now = datetime.now(timezone.utc)
    assert is_expired(exam, now) is False


def test_is_expired_handles_naive_datetime():
    """scheduled_start stored without tzinfo should be treated as UTC."""
    exam = MagicMock()
    exam.state = "open"
    exam.duration_minutes = 60
    # Naive datetime — 70 minutes ago
    exam.scheduled_start = datetime.now(timezone.utc) - timedelta(minutes=70)
    now = datetime.now(timezone.utc)
    assert is_expired(exam, now) is True


# ---------------------------------------------------------------------------
# auto_close_if_expired — with mocked DB and WebSocket broadcast
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_close_transitions_state_and_notifies():
    exam = make_exam(state="open", minutes_ago=70, duration=60)
    db = AsyncMock()

    with patch(
        "app.routers.telemetry.close_exam_sessions",
        new=AsyncMock(return_value=3),
    ):
        result = await auto_close_if_expired(db, exam)

    assert result is True
    assert exam.state == "closed"
    assert exam.closed_at is not None
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_auto_close_returns_false_when_not_expired():
    exam = make_exam(state="open", minutes_ago=30, duration=60)
    db = AsyncMock()

    result = await auto_close_if_expired(db, exam)

    assert result is False
    assert exam.state == "open"
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_auto_close_still_closes_if_ws_broadcast_fails():
    """A WebSocket broadcast failure must not prevent the DB state change."""
    exam = make_exam(state="open", minutes_ago=70, duration=60)
    db = AsyncMock()

    with patch(
        "app.routers.telemetry.close_exam_sessions",
        new=AsyncMock(side_effect=Exception("WS failure")),
    ):
        result = await auto_close_if_expired(db, exam)

    assert result is True
    assert exam.state == "closed"
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_auto_close_already_closed_exam_is_noop():
    exam = make_exam(state="closed", minutes_ago=70, duration=60)
    db = AsyncMock()

    result = await auto_close_if_expired(db, exam)

    assert result is False
    db.commit.assert_not_called()
