"""Tests for auto-open of scheduled exams (AEGIS-104).

A draft exam whose scheduled start has passed opens automatically when a student
reads their sessions — no manual professor action required.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.main import app
from app.models.exam import ExamSession
from app.services.exam_scheduling import is_due

STUDENT_ID = "student-777"

QUIZ = {"title": "Auto Quiz", "description": "d", "duration_minutes": 30}
QUESTION = {"type": "short", "prompt": "Q?"}


def _student_client() -> AsyncClient:
    token = jwt.encode(
        {"sub": STUDENT_ID, "role": "student"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


# ---------------------------------------------------------------------------
# is_due — pure logic
# ---------------------------------------------------------------------------


def _exam(state: str, start: datetime) -> ExamSession:
    return ExamSession(state=state, scheduled_start=start)


def test_is_due_true_when_draft_and_start_passed() -> None:
    now = datetime.now(timezone.utc)
    assert is_due(_exam("draft", now - timedelta(minutes=1)), now) is True


def test_is_due_false_when_start_in_future() -> None:
    now = datetime.now(timezone.utc)
    assert is_due(_exam("draft", now + timedelta(hours=1)), now) is False


def test_is_due_false_when_already_open() -> None:
    now = datetime.now(timezone.utc)
    assert is_due(_exam("open", now - timedelta(hours=1)), now) is False


def test_is_due_false_when_closed() -> None:
    now = datetime.now(timezone.utc)
    assert is_due(_exam("closed", now - timedelta(hours=1)), now) is False


def test_is_due_treats_naive_start_as_utc() -> None:
    now = datetime.now(timezone.utc)
    naive_past = (now - timedelta(minutes=5)).replace(tzinfo=None)
    assert is_due(_exam("draft", naive_past), now) is True


# ---------------------------------------------------------------------------
# Integration — the student sessions list auto-opens a due exam
# ---------------------------------------------------------------------------


async def _make_exam(client: AsyncClient, scheduled_start: str) -> str:
    quiz_id = (await client.post("/quizzes", json=QUIZ)).json()["id"]
    await client.post(f"/quizzes/{quiz_id}/questions", json=QUESTION)
    exam_id = (
        await client.post(
            "/exams",
            json={
                "course_id": "CS",
                "scheduled_start": scheduled_start,
                "duration_minutes": 60,
                "quiz_id": quiz_id,
            },
        )
    ).json()["id"]
    await client.post(
        f"/exams/{exam_id}/enrollments", json={"student_id": STUDENT_ID}
    )
    return exam_id


@pytest.mark.asyncio
async def test_student_sessions_auto_opens_due_exam(client: AsyncClient) -> None:
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    exam_id = await _make_exam(client, past)  # never manually opened

    async with _student_client() as student:
        res = await student.get("/student/sessions")

    assert res.status_code == 200
    by_id = {e["exam_id"]: e for e in res.json()}
    assert by_id[exam_id]["status"] == "open"


@pytest.mark.asyncio
async def test_future_exam_stays_upcoming(client: AsyncClient) -> None:
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    exam_id = await _make_exam(client, future)

    async with _student_client() as student:
        res = await student.get("/student/sessions")

    by_id = {e["exam_id"]: e for e in res.json()}
    assert by_id[exam_id]["status"] == "upcoming"
